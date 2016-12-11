from middlewared.schema import accepts, Int
from middlewared.service import CRUDService
from middlewared.utils import Nid, Popen

import gevent
import netif
import os
import subprocess
import sysctl


class VMManager(object):

    def __init__(self, service):
        self.service = service
        self.logger = self.service.logger
        self._vm = {}

    def start(self, id):
        vm = self.service.query([('id', '=', id)], {'get': True})
        self._vm[id] = VMSupervisor(self, vm)
        gevent.spawn(self._vm[id].run)

    def stop(self, id):
        supervisor = self._vm.get(id)
        if not supervisor:
            return False
        return supervisor.stop()

    def status(self, id):
        supervisor = self._vm.get(id)
        if not supervisor:
            return {
                'state': 'STOPPED',
            }
        else:
            return {
                'state': 'RUNNING',
            }


class VMSupervisor(object):

    def __init__(self, manager, vm):
        self.manager = manager
        self.logger = self.manager.logger
        self.vm = vm
        self.proc = None
        self.taps = []

    def run(self):
        args = [
            'bhyve',
            '-A',
            '-P',
            '-H',
            '-c', str(self.vm['vcpus']),
            '-m', str(self.vm['memory']),
            '-s', '0:0,hostbridge',
            '-s', '31,lpc',
            '-l', 'com1,/dev/nmdm{}A'.format(self.vm['id']),
        ]

        if self.vm['bootloader'] in ('UEFI', 'UEFI_CSM'):
            args += [
                '-l', 'bootrom,/usr/local/share/uefi-firmware/BHYVE_UEFI{}.fd'.format('_CSM' if self.vm['bootloader'] == 'UEFI_CSM' else ''),
            ]

        nid = Nid(3)
        for device in self.vm['devices']:
            if device['dtype'] == 'DISK':
                if device['attributes'].get('mode') == 'AHCI':
                    args += ['-s', '{},ahci-hd,{}'.format(nid(), device['attributes']['path'])]
                else:
                    args += ['-s', '{},virtio-blk,{}'.format(nid(), device['attributes']['path'])]
            elif device['dtype'] == 'CDROM':
                args += ['-s', '{},ahci-cd,{}'.format(nid(), device['attributes']['path'])]
            elif device['dtype'] == 'NIC':
                tapname = netif.create_interface('tap')
                tap = netif.get_interface(tapname)
                tap.up()
                self.taps.append(tapname)
                # If Bridge
                if True:
                    bridge = None
                    for name, iface in netif.list_interfaces().items():
                        if name.startswith('bridge'):
                            bridge = iface
                            break
                    if not bridge:
                        bridge = netif.create_interface('bridge')
                    bridge.add_member(tapname)

                    defiface = Popen("route -nv show default|grep -w interface|awk '{ print $2 }'", stdout=subprocess.PIPE, shell=True).communicate()[0].strip()
                    if defiface and defiface not in bridge.members:
                        bridge.add_member(defiface)
                    bridge.up()
                if device['attributes'].get('type') == 'VIRTIO':
                    nictype = 'virtio-net'
                else:
                    nictype = 'e1000'
                args += ['-s', '{},{},{}'.format(nid(), nictype, tapname)]
            elif device['dtype'] == 'VNC':
                if device['attributes'].get('wait'):
                    wait = 'wait'
                else:
                    wait = ''
                args += [
                    '-s', '29,fbuf,tcp=0.0.0.0:{},w=1024,h=768,{}'.format(5900 + self.vm['id'], wait),
                    '-s', '30,xhci,tablet',
                ]

        args.append(self.vm['name'])

        self.logger.debug('Starting bhyve: {}'.format(' '.join(args)))
        self.proc = Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in self.proc.stdout:
            self.logger.debug('{}: {}'.format(self.vm['name'], line))

        self.proc.wait()

        self.logger.info('Destroying {}'.format(self.vm['name']))

        Popen(['bhyvectl', '--destroy', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE).wait()

        while self.taps:
            netif.destroy_interface(self.taps.pop())

        self.manager._vm.pop(self.vm['id'], None)

    def stop(self):
        if self.proc:
            os.kill(self.proc.pid, 15)
            return True


class VMService(CRUDService):

    class Config:
        namespace = 'vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self._manager = VMManager(self)

    def flags(self):
        data = {}

        vmx = sysctl.filter('hw.vmm.vmx.initialized')
        data['intel_vmx'] = True if vmx and vmx[0].value else False

        ug = sysctl.filter('hw.vmm.vmx.cap.unrestricted_guest')
        data['unrestricted_guest'] = True if ug and ug[0].value else False

        return data

    def query(self, filters=None, options=None):
        options = options or {}
        options['extend'] = 'vm._extend_vm'
        return self.middleware.call('datastore.query', 'vm.vm', filters, options)

    def _extend_vm(self, vm):
        vm['devices'] = []
        for device in self.middleware.call('datastore.query', 'vm.device', [('vm__id', '=', vm['id'])]):
            device.pop('id', None)
            device.pop('vm', None)
            vm['devices'].append(device)
        return vm

    def do_create(self, data):

        devices = data.pop('devices')
        pk = self.middleware.call('datastore.insert', 'vm.vm', data)

        for device in devices:
            device['vm'] = pk
            self.middleware.call('datastore.insert', 'vm.device', device)
        return pk

    def do_update(self, id, data):
        return self.middleware.call('datastore.update', 'vm.vm', id, data)

    def do_delete(self, id):
        return self.middleware.call('datastore.delete', 'vm.vm', id)

    @accepts(Int('id'))
    def start(self, id):
        return self._manager.start(id)

    @accepts(Int('id'))
    def stop(self, id):
        return self._manager.stop(id)

    @accepts(Int('id'))
    def status(self, id):
        return self._manager.status(id)


def kmod_load():
    kldstat = Popen(['/sbin/kldstat'], stdout=subprocess.PIPE).communicate()[0]
    if 'vmm.ko' not in kldstat:
        Popen(['/sbin/kldload', 'vmm'])
    if 'nmdm.ko' not in kldstat:
        Popen(['/sbin/kldload', 'nmdm'])


def setup(middleware):
    gevent.spawn(kmod_load)
