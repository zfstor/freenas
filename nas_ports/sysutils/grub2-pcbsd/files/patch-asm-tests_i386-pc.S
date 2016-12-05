From a0bf403f66dbaca4edd8e667bfc397dd91c8d71c Mon Sep 17 00:00:00 2001
From: Andrei Borzenkov <arvidjaar@gmail.com>
Date: Wed, 28 Sep 2016 20:31:04 +0300
Subject: asm-tests/i386-pc: Check that movl is 5 bytes.

LLVM 3.9 now emits short form of jump instructions, but it is still using
32 bit addresses for some movl instructions. Fortunately it was caught early:

clang ... boot/i386/pc/boot.S
clang -cc1as: fatal error: error in backend: invalid .org offset '440' (at offset '441')

Add additional check to catch it during configure run and force -no-integrated-as.

Closes: 49200

More details in
  https://lists.gnu.org/archive/html/grub-devel/2015-02/msg00099.html
  https://llvm.org/bugs/show_bug.cgi?id=22662
---
 asm-tests/i386-pc.S | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/asm-tests/i386-pc.S.orig b/asm-tests/i386-pc.S
index 97cd32a..43ed157 100644
--- asm-tests/i386-pc.S.orig
+++ asm-tests/i386-pc.S
@@ -5,6 +5,12 @@
 	.code16
 	jmp far
 	.org 4
-	.space 300
+	jmp nearer
+	.org 6
+	movl nearer, %ebx
+	.org 11
+	.space 100
+nearer:
+	.space 200
 far:
 	.byte 0
