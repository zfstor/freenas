import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common import humanize_size
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import PathField
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.vm import models

log = logging.getLogger('vm.forms')


class VMForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.VM

    def save(self, **kwargs):
        with client as c:
            cdata = self.cleaned_data
            if self.instance.id:
                c.call('vm.update', self.instance.id, cdata)
                pk = self.instance.id
            else:
                pk = c.call('vm.create', cdata)
        return models.VM.objects.get(pk=pk)

    def delete(self, **kwargs):
        with client as c:
            c.call('vm.delete', self.instance.id)


class DeviceForm(ModelForm):

    CDROM_path = PathField(
        label=_('CD-ROM (ISO)'),
        required=False,
        dirsonly=False,
        filesonly=True,
    )
    DISK_zvol = forms.ChoiceField(
        label=_('ZVol'),
        required=False,
    )
    DISK_mode = forms.ChoiceField(
        label=_('Mode'),
        choices=(
            ('AHCI', _('AHCI')),
            ('VIRTIO', _('VirtIO')),
        ),
        required=False,
        initial='AHCI',
    )
    NIC_type = forms.ChoiceField(
        label=_('Adapter Type'),
        choices=(
            ('E1000', _('Intel e82545 (e1000)')),
            ('VIRTIO', _('VirtIO')),
        ),
        required=False,
        initial='E1000',
    )
    VNC_wait = forms.BooleanField(
        label=_('Wait to boot'),
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.Device

    def __init__(self, *args, **kwargs):
        super(DeviceForm, self).__init__(*args, **kwargs)
        self.fields['dtype'].widget.attrs['onChange'] = (
            "deviceTypeToggle();"
        )

        diskchoices = {}
        _n = notifier()
        used_zvol = []
        for volume in Volume.objects.filter():
            zvols = _n.list_zfs_vols(volume.vol_name, sort='name')
            for zvol, attrs in zvols.items():
                if "zvol/" + zvol not in used_zvol:
                    diskchoices["zvol/" + zvol] = "%s (%s)" % (
                        zvol,
                        humanize_size(attrs['volsize']))
        self.fields['DISK_zvol'].choices = diskchoices.items()

        if self.instance.id:
            if self.instance.dtype == 'CDROM':
                self.fields['CDROM_path'].initial = self.instance.attributes.get('path', '')
            elif self.instance.dtype == 'DISK':
                self.fields['DISK_zvol'].initial = self.instance.attributes.get('path', '').replace('/dev/', '')
            elif self.instance.dtype == 'NIC':
                self.fields['NIC_type'].initial = self.instance.attributes.get('type')
            elif self.instance.dtype == 'VNC':
                self.fields['VNC_wait'].initial = self.instance.attributes.get('wait')

    def clean(self):
        vm = self.cleaned_data.get('vm')
        if self.cleaned_data.get('dtype') == 'VNC':
            if vm and vm.bootloader not in ('UEFI', 'UEFI_CSM'):
                self._errors['dtype'] = self.error_class([
                    _('VNC is only allowed for UEFI')
                ])
                self.cleaned_data.pop('dtype', None)
        return self.cleaned_data

    def save(self, *args, **kwargs):
        kwargs['commit'] = False
        obj = super(DeviceForm, self).save(*args, **kwargs)
        if self.cleaned_data['dtype'] == 'DISK':
            obj.attributes = {
                'path': '/dev/' + self.cleaned_data['DISK_zvol'],
            }
        elif self.cleaned_data['dtype'] == 'CDROM':
            obj.attributes = {
                'path': self.cleaned_data['CDROM_path'],
            }
        elif self.cleaned_data['dtype'] == 'NIC':
            obj.attributes = {
                'type': self.cleaned_data['NIC_type'],
            }
        elif self.cleaned_data['dtype'] == 'VNC':
            obj.attributes = {
                'wait': self.cleaned_data['VNC_wait'],
            }
        obj.save()
        return obj
