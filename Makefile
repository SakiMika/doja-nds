# DoJa standalone NDS KVM build.
# This source tree is independent from the PSTros project branch.
# Supports current libnds/Calico/libdvm and older split libfat layouts
# without requiring project-specific devkitPro paths.

TARGET       := unprepared_doja_v36
BUILD        := build
SOURCES      := source
INCLUDES     := include \
                kvm/VmCommon/h \
                kvm/VmSkel/h \
                kvm/VmExtra/h \
                jam/h \
                kvm/VmCommon/src
EMBEDDED_JAR := embedded/game.jar
EMBEDDED_AUDIO := embedded/osnd_native.pcm
EMBEDDED_SCRATCHPAD := embedded/doja_scratchpad.bin
TEXT1        := J2ME Game
TEXT2        := J2ME Standalone
TEXT3        := MIDlet
NDS_GAME_CODE := \#\#\#\#
NDS_MAKER_CODE := HB
NDS_INTERNAL_TITLE := J2MEGAME
NDS_ICON := assets/standalone_icon.bmp

# build_doja.bat regenerates this file for the selected DoJa game before make starts.
-include standalone_game.mk

# build_with_log.ps1 passes a real POSIX path such as /d/devkitPro. Keep a
# fallback for users who invoke make directly from the devkitPro MSYS2 shell.
ifeq ($(strip $(DEVKITPRO)),)
  ifneq ($(wildcard /opt/devkitpro/devkitARM),)
    DEVKITPRO := /opt/devkitpro
  else ifneq ($(wildcard /d/devkitPro/devkitARM),)
    DEVKITPRO := /d/devkitPro
  else ifneq ($(wildcard /c/devkitPro/devkitARM),)
    DEVKITPRO := /c/devkitPro
  else
    $(error DEVKITPRO is not set and devkitPro was not found)
  endif
endif
DEVKITARM := $(DEVKITPRO)/devkitARM

# Support both old arm-eabi-* and modern arm-none-eabi-* devkitARM prefixes.
ifneq ($(wildcard $(DEVKITARM)/bin/arm-eabi-gcc*),)
  PREFIX := $(DEVKITARM)/bin/arm-eabi-
else
  PREFIX := $(DEVKITARM)/bin/arm-none-eabi-
endif
CC      := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy
NDSTOOL ?= ndstool

ARCH    := -march=armv5te -mtune=arm946e-s -mthumb -mthumb-interwork

# libnds 2.x is built on Calico. Its current ARM9 linker specification is
# calico/share/ds9.specs.
CALICO  := $(DEVKITPRO)/calico
SPECS   := -specs=$(CALICO)/share/ds9.specs

DEFS := -D__NDS__ -DARM9 -DNDS -DUNIX -DLINUX -D__arm__ \
        -DUSE_KNI=1 -DENABLE_JAVA_DEBUGGER=0 -DPADTABLE=1 \
        -DDISABLE_VERIFIER -DPRINT_BACKTRACE=1 -DCONSOLE_MD \
        -DENABLE_HEAP_COMPACTION=0 -DCHUNKY_HEAP=0 \
        -DPLATFORMNAME='"j2me"' -DDOJA_NATIVE_SCRATCHPAD=1

# FAT is optional at runtime and is used only for RMS saves. The game JAR is
# linked directly into ARM9, so this standalone target has no NitroFS or
# libfilesystem dependency. Detect both current and older libfat layouts.
LIBNDS_INC := $(DEVKITPRO)/libnds/include
LIBNDS_LIB := $(DEVKITPRO)/libnds/lib
CALICO_INC := $(CALICO)/include
CALICO_LIB := $(CALICO)/lib

FAT_INC := $(firstword $(foreach d,$(LIBNDS_INC) $(DEVKITPRO)/libfat/include,$(if $(wildcard $(d)/fat.h),$(d))))
FAT_LIB := $(firstword $(foreach d,$(LIBNDS_LIB) $(DEVKITPRO)/libfat/lib,$(if $(wildcard $(d)/libfat.a),$(d))))
STORAGE_INCS := $(sort $(FAT_INC))
STORAGE_LIBS := $(sort $(FAT_LIB))

ARM7_ELF := $(CALICO)/bin/ds7_maine.elf
# Do not redirect printf/fprintf/sprintf with command-line object macros.
# include/kvm_stdio_redirect.h first loads stdio normally, then installs safe
# function-like redirects for KVM source calls only.
CFLAGS  := $(ARCH) -std=gnu99 -O2 -g -ffunction-sections -fdata-sections -fcommon \
           -Wall -Wno-unused-function -Wno-unused-variable -Wno-missing-braces \
           -Wno-pointer-sign -Wno-implicit-function-declaration \
           -Wno-incompatible-pointer-types -Wno-builtin-declaration-mismatch \
           -Wno-strict-aliasing -Wno-dangling-pointer -Wno-misleading-indentation \
           $(DEFS) $(addprefix -I,$(INCLUDES)) -I$(CALICO_INC) -I$(LIBNDS_INC) \
           $(addprefix -I,$(STORAGE_INCS)) -include include/kvm_stdio_redirect.h
LDFLAGS := $(ARCH) $(SPECS) -Wl,-Map,$(BUILD)/$(TARGET).map -Wl,--gc-sections
LIBS    := $(addprefix -L,$(STORAGE_LIBS)) -L$(LIBNDS_LIB) -L$(CALICO_LIB) \
           -lfat -lnds9 -lcalico_ds9 -lm -lgcc

CFILES := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
OFILES := $(CFILES:.c=.o)
OBJS   := $(addprefix $(BUILD)/,$(OFILES)) $(BUILD)/embedded_game_jar.o $(BUILD)/embedded_doja_scratchpad_bin.o $(BUILD)/embedded_osnd_native_pcm.o

vpath %.c $(SOURCES)

.PHONY: all clean check env restore-native-scratchpad

all: check $(TARGET).nds

# v36 safety net: make can restore the separately linked ScratchPad from the
# preparation backup.  This prevents a stale game.jar from being built after
# users extract a newer source package over an older working directory.
restore-native-scratchpad:
	@if [ ! -f "$(EMBEDDED_SCRATCHPAD)" ] && [ -f "build_doja/doja_scratchpad.bin" ]; then \
		echo "[RESTORE] $(EMBEDDED_SCRATCHPAD) from build_doja backup"; \
		mkdir -p embedded; \
		cp "build_doja/doja_scratchpad.bin" "$(EMBEDDED_SCRATCHPAD)"; \
	fi

check: restore-native-scratchpad
	@echo "DEVKITPRO=$(DEVKITPRO)"
	@echo "DEVKITARM=$(DEVKITARM)"
	@echo "FAT header=$(if $(FAT_INC),$(FAT_INC)/fat.h,NOT FOUND)"
	@echo "FAT library=$(if $(FAT_LIB),$(FAT_LIB)/libfat.a,NOT FOUND)"
	@echo "[CHECK] DoJa port version: v36"
	@test -f include/doja_port_version.h || (echo "Missing source version header"; exit 1)
	@grep -q "^#define DOJA_SOURCE_PORT_VERSION 36$$" include/doja_port_version.h || (echo "Wrong source version header; expected v36"; exit 1)
	@grep -q "DOJA_PORT_BUILD_VERSION != DOJA_SOURCE_PORT_VERSION" kvm/VmSkel/src/nds_main.c || (echo "Stale NDS metadata version guard"; exit 1)
	@echo "[CHECK] Connector platform: j2me"
	@echo "[CHECK] Encoding: microedition.encoding=SJIS; CP932 decode/encode; full font"
	@test -x "$(CC)" || (echo "Missing devkitARM compiler: $(CC)"; exit 1)
	@test -f "$(CALICO_INC)/calico.h" || (echo "Missing Calico headers: $(CALICO_INC)"; echo "Install/update with: pacman -Syu --needed nds-dev"; exit 1)
	@test -n "$(FAT_INC)" || (echo "Missing fat.h. Checked $(LIBNDS_INC) and $(DEVKITPRO)/libfat/include"; echo "Install/update with: pacman -Syu --needed nds-dev"; exit 1)
	@test -n "$(FAT_LIB)" || (echo "Missing libfat.a. Checked $(LIBNDS_LIB) and $(DEVKITPRO)/libfat/lib"; echo "Install/update with: pacman -Syu --needed nds-dev"; exit 1)
	@test -f "$(CALICO)/share/ds9.specs" || (echo "Missing Calico ARM9 specs: $(CALICO)/share/ds9.specs"; exit 1)
	@test -f "$(ARM7_ELF)" || (echo "Missing default ARM7 binary: $(ARM7_ELF)"; exit 1)
	@test -f "build_doja/prepared_v36.ok" || (echo "Missing v36 preparation marker. Run build_doja.bat"; exit 1)
	@grep -q '^TARGET := .*_doja_v36$$' standalone_game.mk || (echo "Wrong/stale standalone_game.mk; expected v36"; exit 1)
	@grep -q '^#define DOJA_PORT_BUILD_VERSION 36$$' include/standalone_game.h || (echo "Wrong/stale standalone_game.h; expected v36"; exit 1)

	@grep -Fq 'NDS_GAME_CODE := \#\#\#\#' standalone_game.mk || (echo "ROM header must use homebrew game code #### for DLDI patching"; exit 1)
	@grep -Fq '#define STANDALONE_NDS_GAME_CODE "####"' include/standalone_game.h || (echo "Generated NDS header code is not homebrew-safe"; exit 1)
	@grep -Eq '^#define STANDALONE_APP_STORAGE_CODE "[A-Z0-9]{4}"$$' include/standalone_game.h || (echo "Missing original app storage code"; exit 1)
	@! grep -q 'doja/scratchpad.bin' kvm/VmExtra/src/loaderFile.c || (echo "Legacy ScratchPad resource bridge still present"; exit 1)
	@test -f "$(EMBEDDED_JAR)" || (echo "Missing embedded JAR: $(EMBEDDED_JAR)"; exit 1)
	@test -f "$(EMBEDDED_AUDIO)" || (echo "Missing native PCM pack: $(EMBEDDED_AUDIO)"; exit 1)
	@test -f "$(EMBEDDED_SCRATCHPAD)" || (echo "Missing native ScratchPad: $(EMBEDDED_SCRATCHPAD)"; exit 1)
	@grep -q '#define DOJA_LATE_NATIVE_BIND 1' kvm/VmCommon/src/native.c || (echo "Missing v36 ROMIZING late-native bridge"; exit 1)
	@grep -q 'getDoJaLateNativeFunction(clazz, methodName, methodSignature)' kvm/VmCommon/src/native.c || (echo "Late-native bridge is not called by getNativeFunction"; exit 1)
	@grep -q 'scratchpad_Protocol_nativeReadBytes' kvm/VmSkel/src/nativeFunctionTableGBA.c || (echo "Missing non-ROMIZING ScratchPad native table"; exit 1)
	@grep -q 'DoJa v36 ScratchPad ROM access with persistent same-name .sav saves' kvm/VmExtra/src/resource.c || (echo "Missing v36 ScratchPad backend"; exit 1)
	@grep -q 'dojaSpPersistenceFlush' kvm/VmExtra/src/resource.c || (echo "Missing v36 persistent save flush"; exit 1)
	@grep -q 'dojaSpEnsurePersistence' kvm/VmExtra/src/resource.c || (echo "Missing v36 lazy storage retry"; exit 1)
	@grep -q 'dojaSaveUiResult' kvm/VmExtra/src/resource.c || (echo "Missing v36 save-result status"; exit 1)
	@grep -q 'dojaSpCopyFile' kvm/VmExtra/src/resource.c || (echo "Missing v36 libfat fallback"; exit 1)
	@! grep -q 'fsync(fileno' kvm/VmExtra/src/resource.c || (echo "Unsupported fsync call still present"; exit 1)
	@grep -q 'memcpy(dojaSpTempPath + length - 4, ".TMP", 5)' kvm/VmExtra/src/resource.c || (echo "Missing v36 .TMP save path"; exit 1)
	@grep -q 'DOJA_CP_SLOT_BASE 5' kvm/VmExtra/src/resource.c || (echo "Wrong v36 Corpse Party slot offsets"; exit 1)
	@grep -q 'Protocol.nativeFlush()' doja_port/doja_src/com/sun/cldc/io/j2me/scratchpad/ScratchpadOutputStream.java || (echo "Output stream does not flush save"; exit 1)
	@test -f assets/default_standalone_icon.bmp || (echo "Missing bundled default icon"; exit 1)
	@test -f doja_port/doja_src/com/sun/cldc/io/j2me/scratchpad/ScratchpadInputStream.java || (echo "Missing v36 separate ScratchpadInputStream source"; exit 1)
	@test -f doja_port/doja_src/com/sun/cldc/io/j2me/scratchpad/SegmentToken.java || (echo "Missing v36 SegmentToken source"; exit 1)
	@test -f doja_port/doja_src/com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream.java || (echo "Missing v36 zero-copy segment stream source"; exit 1)
	@test -f tools/segment_stream_patch.py || (echo "Missing v36 j.class segment patcher"; exit 1)
	@grep -q 'KVM HEAP OOM req=' kvm/VmCommon/src/collector.c || (echo "Missing v36 heap OOM diagnostics"; exit 1)
	@grep -q '^#define DEFAULTHEAPSIZE (2432\*1024)$$' kvm/VmSkel/h/machine_md.h || (echo "Wrong v36 Java heap size; expected 2432 KiB"; exit 1)
	@grep -q 'DoJa v36 heap allocated:' kvm/VmSkel/src/nds_runtime.c || (echo "Missing v36 heap allocation diagnostics"; exit 1)
	@grep -q 'ConfigData.configActive = false' doja_port/doja_src/nds/doja/MainApp.java || (echo "Missing v36 MIDP action-mode input fix"; exit 1)
	@grep -q 'case -2: return KEY_DOWN' doja_port/doja_src/com/nttdocomo/ui/Canvas.java || (echo "Missing v36 negative-key fallback mapping"; exit 1)
	@grep -q 'def full_cp932_repertoire()' tools/fontgen.py || (echo "Missing v36 full CP932 font + SJIS decode generator"; exit 1)
	@grep -q 'chars.update(full_cp932_repertoire())' tools/fontgen.py || (echo "v36 CP932 repertoire is not enabled"; exit 1)
	@grep -q 'DoJa font ready: glyphs=' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 font-load diagnostics"; exit 1)
	@grep -q 'FONT MISS U+' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 missing-glyph diagnostics"; exit 1)
	@grep -q 'value = "SJIS";' kvm/VmCommon/src/property.c || (echo "microedition.encoding is not SJIS"; exit 1)
	@test -f tools/cp932gen.py || (echo "Missing v36 CP932 table generator"; exit 1)
	@test -f doja_port/doja_src/nds/doja/encoding/Cp932Codec.java || (echo "Missing v36 CP932 codec"; exit 1)
	@test -f doja_port/doja_src/com/sun/cldc/i18n/j2me/SJIS_Reader.java || (echo "Missing v36 SJIS reader"; exit 1)
	@test -f doja_port/doja_src/com/sun/cldc/i18n/j2me/SJIS_Writer.java || (echo "Missing v36 SJIS writer"; exit 1)
	@grep -q 'Cp932Codec.normalizeForDisplay' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 raw-SJIS display fallback"; exit 1)
	@grep -q 'isNonPrintingControl' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 NUL/control padding suppression"; exit 1)
	@grep -q 'return c < 0x0020 || c == 0x007F' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "v36 control padding predicate is stale"; exit 1)
	@grep -q 'nul-padding-skip' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 font diagnostic marker"; exit 1)
	@grep -Fq 'target_w = (width + 1) // 2 if ord(char) <= 0x007F else width' tools/fontgen.py || (echo "Missing v36 Latin half-cell font generation"; exit 1)
	@grep -Fq 'int sourceWidth = c <= 0x007F ? (baseWidth + 1) / 2 : baseWidth' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 Latin continuous-source renderer"; exit 1)
	@grep -q 'latin-half-cell-preserve' doja_port/doja_src/nds/doja/font/BitmapJapaneseFont.java || (echo "Missing v36 Latin font marker"; exit 1)
	@! grep -qi 'nftr' tools/fontgen.py || (echo "NFTR hybrid font must remain disabled in v36"; exit 1)
	@grep -q 'EmuCanvas.screenPosX = 0' doja_port/doja_src/nds/doja/MainApp.java || (echo "Missing v36 full-screen X origin"; exit 1)
	@grep -q 'EmuCanvas.screenPosY = 0' doja_port/doja_src/nds/doja/MainApp.java || (echo "Missing v36 full-screen Y origin"; exit 1)
	@grep -q 'DoJa v36 forced final-frame resize' kvm/VmSkel/src/Java_nds_Video.c || (echo "Missing v36 native final-frame scaler"; exit 1)
	@grep -Fq 'srcW == 240 && srcH == 240 && dstW == 256 && dstH == 192' kvm/VmSkel/src/Java_nds_Video.c || (echo "Wrong v36 scaler dimensions"; exit 1)
	@grep -Fq 'goto blit_done;' kvm/VmSkel/src/Java_nds_Video.c || (echo "Missing v36 common scaler epilogue jump"; exit 1)
	@grep -q '^blit_done:' kvm/VmSkel/src/Java_nds_Video.c || (echo "Missing v36 common scaler epilogue label"; exit 1)
	@grep -q -- '-DENABLE_HEAP_COMPACTION=0' Makefile || (echo "v36 requires heap compaction disabled"; exit 1)
	@grep -q 'return new ScratchpadInputStream' doja_port/doja_src/com/sun/cldc/io/j2me/scratchpad/Protocol.java || (echo "Protocol still returns itself as InputStream"; exit 1)
	@! grep -q 'extends InputStream' doja_port/doja_src/com/sun/cldc/io/j2me/scratchpad/Protocol.java || (echo "Protocol must not extend InputStream in v36"; exit 1)
	@test -f "$(NDS_ICON)" || (echo "Missing generated NDS icon: $(NDS_ICON)"; echo "Run build.bat to prepare it from the JAR"; exit 1)
	@test -f "include/standalone_game.h" || (echo "Missing generated game config: include/standalone_game.h"; echo "Run build.bat"; exit 1)
	@grep -Fq 'static int pstrosConfigureSaveStorageOn(const char *volume, const char *backend)' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing multi-backend save probe"; exit 1)
	@grep -Fq 'int pstrosMountSaveStorageAuto(const char *launchPath)' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing argv-aware save mount"; exit 1)
	@grep -q 'fatInitDefault()' kvm/VmSkel/src/Java_nds_File.c || (echo "Supported libdvm/libfat initialization is missing"; exit 1)
	@grep -q 'pstrosFatInitAttempted' kvm/VmSkel/src/Java_nds_File.c || (echo "One-shot libdvm initialization guard is missing"; exit 1)
	@grep -q 'pstrosProbeMountedVolumes(0)' kvm/VmSkel/src/Java_nds_File.c || (echo "Existing-volume probe is missing"; exit 1)
	@grep -q 'pstrosProbeMountedVolumes(1)' kvm/VmSkel/src/Java_nds_File.c || (echo "Post-libdvm volume probe is missing"; exit 1)
	@! grep -q '_FAT_disc_interfaces' kvm/VmSkel/src/Java_nds_File.c || (echo "Private libfat interface table must not be referenced"; exit 1)
	@! grep -q 'dldiGetInternal' kvm/VmSkel/src/Java_nds_File.c || (echo "Removed DLDI getter must not be linked directly"; exit 1)
	@! grep -q 'get_io_dsisd' kvm/VmSkel/src/Java_nds_File.c || (echo "Removed DSi-SD getter must not be linked directly"; exit 1)
	@! grep -q 'fatMountSimple(' kvm/VmSkel/src/Java_nds_File.c || (echo "Manual private-interface mounts must not be used"; exit 1)
	@grep -q 'fopen(probePath, "wb")' kvm/VmSkel/src/Java_nds_File.c || (echo "Writable stdio save probe is missing"; exit 1)

	@grep -q 'STANDALONE_SHORT_SAVE_NAME' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing v36 SAV fallback path"; exit 1)
	@grep -q 'pstrosRememberLaunchSavePath' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing same-name SAV path derivation"; exit 1)
	@grep -q 'pstrosChooseFinalSavePath' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing same-name SAV path selection"; exit 1)
	@grep -q 'MODE: SAV FILE' kvm/VmSkel/src/nds_main.c || (echo "Missing SAV mode status"; exit 1)
	@grep -q 'SAVE: READY' kvm/VmSkel/src/nds_main.c || (echo "Missing compact save status UI"; exit 1)
	@grep -q 'pstrosSetVmConsoleEnabled(0)' kvm/VmSkel/src/nds_main.c || (echo "Verbose VM console is still enabled"; exit 1)
	@! grep -q 'POLL n=' kvm/VmSkel/src/Java_nds_Key.c || (echo "Input debug spam is still enabled"; exit 1)
	@grep -q 'pstrosMountSaveStorageAuto(launchPath)' kvm/VmSkel/src/nds_main.c || (echo "NDS entry point is not using argv-aware save mount"; exit 1)
	@grep -q 'MEDIA: %s' kvm/VmSkel/src/nds_main.c || (echo "Save backend status is missing"; exit 1)
	@grep -q 'STAGE: %s' kvm/VmSkel/src/nds_main.c || (echo "Save mount-stage status is missing"; exit 1)
	@! grep -q 'fatInitDefault()' kvm/VmSkel/src/nds_main.c || (echo "Storage initialization must remain inside the save backend"; exit 1)
	@grep -q 'STANDALONE_RMS_SAVE_PATH' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing v36 separate RMS path"; exit 1)
	@grep -q '^const char \*pstrosGetSavePath(void)' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing pstrosGetSavePath implementation"; exit 1)
	@grep -q '^int pstrosGetSaveErrno(void)' kvm/VmSkel/src/Java_nds_File.c || (echo "Missing pstrosGetSaveErrno implementation"; exit 1)
	@command -v $(NDSTOOL) >/dev/null 2>&1 || (echo "Missing ndstool in PATH"; exit 1)

# This target is intentionally verbose so last_build.log shows every resolved
# SDK path when a future toolchain update changes the layout.
env:
	@echo "TARGET=$(TARGET)"
	@echo "BUILD=$(BUILD)"
	@echo "SOURCES=$(SOURCES)"
	@echo "INCLUDES=$(INCLUDES)"
	@echo "CC=$(CC)"
	@echo "DEVKITPRO=$(DEVKITPRO)"
	@echo "LIBNDS_INC=$(LIBNDS_INC)"
	@echo "LIBNDS_LIB=$(LIBNDS_LIB)"
	@echo "FAT_INC=$(FAT_INC)"
	@echo "FAT_LIB=$(FAT_LIB)"
	@echo "EMBEDDED_JAR=$(EMBEDDED_JAR)"
	@echo "EMBEDDED_AUDIO=$(EMBEDDED_AUDIO)"
	@echo "EMBEDDED_SCRATCHPAD=$(EMBEDDED_SCRATCHPAD)"

$(TARGET).nds: $(BUILD)/$(TARGET).elf
	$(NDSTOOL) -c $@ -9 $< -7 $(ARM7_ELF) -b $(NDS_ICON) \
		"$(TEXT1);$(TEXT2);$(TEXT3)" \
		-g "$(NDS_GAME_CODE)" $(NDS_MAKER_CODE) $(NDS_INTERNAL_TITLE) 0


# Link the selected JAR directly into the ARM9 executable. The generated
# symbols are _binary_embedded_game_jar_start/end and are consumed by the
# memory-backed KVM JAR loader.
$(BUILD)/embedded_game_jar.o: $(EMBEDDED_JAR) | $(BUILD)
	cp $< $(BUILD)/embedded_game.jar
	cd $(BUILD) && $(OBJCOPY) -I binary -O elf32-littlearm -B arm \
		--rename-section .data=.rodata,alloc,load,readonly,data,contents \
		embedded_game.jar embedded_game_jar.o

# Link DoJa ScratchPad outside game.jar. The separate input stream exposes this ROM
# data through a non-owning stream, so no 409600-byte KVM heap allocation is
# made while the game loads its offline data.
$(BUILD)/embedded_doja_scratchpad_bin.o: $(EMBEDDED_SCRATCHPAD) | $(BUILD)
	cp $< $(BUILD)/embedded_doja_scratchpad.bin
	cd $(BUILD) && $(OBJCOPY) -I binary -O elf32-littlearm -B arm \
		--rename-section .data=.rodata,alloc,load,readonly,data,contents \
		embedded_doja_scratchpad.bin embedded_doja_scratchpad_bin.o

# Link pre-rendered signed PCM outside the JAR. Diamond Rush keeps its compact
# MIDI resources in Java memory; the native bridge selects the matching track
# without allocating the large PCM data in the KVM heap.
$(BUILD)/embedded_osnd_native_pcm.o: $(EMBEDDED_AUDIO) | $(BUILD)
	cp $< $(BUILD)/embedded_osnd_native.pcm
	cd $(BUILD) && $(OBJCOPY) -I binary -O elf32-littlearm -B arm \
		--rename-section .data=.rodata,alloc,load,readonly,data,contents \
		embedded_osnd_native.pcm embedded_osnd_native_pcm.o

# Link the known-good first-boot RMS template into ARM9 as read-only data.
$(BUILD)/$(TARGET).elf: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^ $(LIBS)

# printf.c implements the redirected functions, so do not apply the call macros
# while compiling that one translation unit.
$(BUILD)/vmskel_05_printf.o: CFLAGS += -DKVM_STDIO_IMPLEMENTATION=1

$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD) *_doja_v*.nds unprepared_doja_v36.nds
