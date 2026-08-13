# DoJa v59 Empty — generic JAR/JAM/SP builder.
# build-doja.bat converts the selected ScratchPad to embedded Nintendo LZ77
# and stores every game.jar entry uncompressed for fast class loading.

TARGET       := unprepared
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
EMBEDDED_SCRATCHPAD := embedded/doja_scratchpad.lz7b
TEXT1        := J2ME Game
TEXT2        := J2ME Standalone
TEXT3        := MIDlet
NDS_GAME_CODE := \#\#\#\#
NDS_MAKER_CODE := HB
NDS_INTERNAL_TITLE := J2MEGAME
NDS_ICON := assets/standalone_icon.bmp

-include standalone_game.mk

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

ifneq ($(wildcard $(DEVKITARM)/bin/arm-eabi-gcc*),)
  PREFIX := $(DEVKITARM)/bin/arm-eabi-
else
  PREFIX := $(DEVKITARM)/bin/arm-none-eabi-
endif
CC      := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy
NDSTOOL ?= ndstool

ARCH    := -march=armv5te -mtune=arm946e-s -mthumb -mthumb-interwork
CALICO  := $(DEVKITPRO)/calico
SPECS   := -specs=$(CALICO)/share/ds9.specs

DEFS := -D__NDS__ -DARM9 -DNDS -DUNIX -DLINUX -D__arm__ \
        -DUSE_KNI=1 -DENABLE_JAVA_DEBUGGER=0 -DPADTABLE=1 \
        -DDISABLE_VERIFIER -DPRINT_BACKTRACE=1 -DCONSOLE_MD \
        -DENABLE_HEAP_COMPACTION=0 -DCHUNKY_HEAP=0 \
        -DPLATFORMNAME='"j2me"' -DDOJA_NATIVE_SCRATCHPAD=1

LIBNDS_INC := $(DEVKITPRO)/libnds/include
LIBNDS_LIB := $(DEVKITPRO)/libnds/lib
CALICO_INC := $(CALICO)/include
CALICO_LIB := $(CALICO)/lib
FAT_INC := $(firstword $(foreach d,$(LIBNDS_INC) $(DEVKITPRO)/libfat/include,$(if $(wildcard $(d)/fat.h),$(d))))
FAT_LIB := $(firstword $(foreach d,$(LIBNDS_LIB) $(DEVKITPRO)/libfat/lib,$(if $(wildcard $(d)/libfat.a),$(d))))
ARM7_ELF := $(CALICO)/bin/ds7_maine.elf

CFLAGS  := $(ARCH) -std=gnu99 -O2 -g -ffunction-sections -fdata-sections -fcommon \
           -Wall -Wno-unused-function -Wno-unused-variable -Wno-missing-braces \
           -Wno-pointer-sign -Wno-implicit-function-declaration \
           -Wno-incompatible-pointer-types -Wno-builtin-declaration-mismatch \
           -Wno-strict-aliasing -Wno-dangling-pointer -Wno-misleading-indentation \
           $(DEFS) $(addprefix -I,$(INCLUDES)) -I$(CALICO_INC) -I$(LIBNDS_INC) \
           $(if $(FAT_INC),-I$(FAT_INC)) -include include/kvm_stdio_redirect.h
LDFLAGS := $(ARCH) $(SPECS) -Wl,-Map,$(BUILD)/$(TARGET).map -Wl,--gc-sections
LIBS    := -L$(LIBNDS_LIB) -L$(DEVKITPRO)/libfat/lib -L$(CALICO_LIB) \
           -lfat -lnds9 -lcalico_ds9 -lm -lgcc

CFILES := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
OFILES := $(CFILES:.c=.o)
OBJS   := $(addprefix $(BUILD)/,$(OFILES)) \
          $(BUILD)/embedded_game_jar.o \
          $(BUILD)/embedded_doja_scratchpad_lz7b.o \
          $(BUILD)/embedded_osnd_native_pcm.o

vpath %.c $(SOURCES)

.PHONY: all clean check env
all: check $(TARGET).nds

check:
	@echo "DEVKITPRO=$(DEVKITPRO)"
	@echo "DEVKITARM=$(DEVKITARM)"
	@echo "FAT header=$(if $(FAT_INC),$(FAT_INC)/fat.h,NOT FOUND)"
	@echo "FAT library=$(if $(FAT_LIB),$(FAT_LIB)/libfat.a,NOT FOUND)"
	@echo "[CHECK] DoJa port version: v59"
	@test -x "$(CC)" || (echo "Missing devkitARM compiler: $(CC)"; exit 1)
	@test -f "$(CALICO_INC)/calico.h" || (echo "Missing Calico headers"; exit 1)
	@test -n "$(FAT_INC)" || (echo "Missing fat.h"; exit 1)
	@test -n "$(FAT_LIB)" || (echo "Missing libfat.a"; exit 1)
	@test -f "$(CALICO)/share/ds9.specs" || (echo "Missing Calico ARM9 specs"; exit 1)
	@test -f "$(ARM7_ELF)" || (echo "Missing ARM7 binary"; exit 1)
	@test -f "build_doja/prepared_v59.ok" || (echo "Missing v59 preparation marker"; exit 1)
	@grep -Eq '^TARGET := [a-z0-9_]+$$' standalone_game.mk || (echo "Wrong standalone_game.mk"; exit 1)
	@grep -q '^#define DOJA_SOURCE_PORT_VERSION 59$$' include/doja_port_version.h || (echo "Wrong source version"; exit 1)
	@grep -q '^#define DOJA_PORT_BUILD_VERSION 59$$' include/standalone_game.h || (echo "Wrong generated version"; exit 1)
	@test -f doja_port/doja_src/nds/doja/image/IndexedBmpDecoder.java || (echo "Missing v59 indexed BMP decoder"; exit 1)
	@grep -q '0x7C1F' kvm/VmSkel/src/Java_nds_Video.c || (echo "Missing Pstros magenta transparency fix"; exit 1)
	@test -f "$(EMBEDDED_JAR)" || (echo "Missing $(EMBEDDED_JAR)"; exit 1)
	@test -f "$(EMBEDDED_AUDIO)" || (echo "Missing $(EMBEDDED_AUDIO)"; exit 1)
	@test -f "$(EMBEDDED_SCRATCHPAD)" || (echo "Missing $(EMBEDDED_SCRATCHPAD)"; exit 1)
	@test "$$(wc -c < "$(EMBEDDED_SCRATCHPAD)")" -eq "$$(awk '/DOJA_SCRATCHPAD_WRAPPER_SIZE/{print $$3; exit}' include/standalone_game.h)" || (echo "ScratchPad wrapper size mismatch"; exit 1)
	@grep -q '_binary_embedded_doja_scratchpad_lz7b_start' kvm/VmExtra/src/resource.c || (echo "Missing embedded LZ77 ScratchPad backend"; exit 1)
	@grep -q 'dojaSpLz77Decode' kvm/VmExtra/src/resource.c || (echo "Missing native LZ77 decoder"; exit 1)
	@! grep -q 'nitroFSInit' kvm/VmSkel/src/nds_main.c || (echo "Blocking NitroFS boot path still present"; exit 1)
	@command -v $(NDSTOOL) >/dev/null 2>&1 || (echo "Missing ndstool in PATH"; exit 1)

$(TARGET).nds: $(BUILD)/$(TARGET).elf
	$(NDSTOOL) -c $@ -9 $< -7 $(ARM7_ELF) -b $(NDS_ICON) \
		"$(TEXT1);$(TEXT2);$(TEXT3)" \
		-g "$(NDS_GAME_CODE)" $(NDS_MAKER_CODE) $(NDS_INTERNAL_TITLE) 0

$(BUILD)/embedded_game_jar.o: $(EMBEDDED_JAR) | $(BUILD)
	cp $< $(BUILD)/embedded_game.jar
	cd $(BUILD) && $(OBJCOPY) -I binary -O elf32-littlearm -B arm \
		--rename-section .data=.rodata,alloc,load,readonly,data,contents \
		embedded_game.jar embedded_game_jar.o

$(BUILD)/embedded_doja_scratchpad_lz7b.o: $(EMBEDDED_SCRATCHPAD) | $(BUILD)
	cp $< $(BUILD)/embedded_doja_scratchpad.lz7b
	cd $(BUILD) && $(OBJCOPY) -I binary -O elf32-littlearm -B arm \
		--rename-section .data=.rodata,alloc,load,readonly,data,contents \
		embedded_doja_scratchpad.lz7b embedded_doja_scratchpad_lz7b.o

$(BUILD)/embedded_osnd_native_pcm.o: $(EMBEDDED_AUDIO) | $(BUILD)
	cp $< $(BUILD)/embedded_osnd_native.pcm
	cd $(BUILD) && $(OBJCOPY) -I binary -O elf32-littlearm -B arm \
		--rename-section .data=.rodata,alloc,load,readonly,data,contents \
		embedded_osnd_native.pcm embedded_osnd_native_pcm.o

$(BUILD)/$(TARGET).elf: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^ $(LIBS)

HOT_ARM_OBJECTS := $(BUILD)/vmcommon_08_interpret.o $(BUILD)/vmcommon_09_execute.o \
                   $(BUILD)/vmcommon_01_cache.o $(BUILD)/vmcommon_10_loader.o \
                   $(BUILD)/vmcommon_17_stackmap.o \
                   $(BUILD)/vmextra_01_jar.o $(BUILD)/vmextra_02_inflate.o \
                   $(BUILD)/vmextra_03_resource.o $(BUILD)/vmskel_17_Java_nds_Video.o
$(HOT_ARM_OBJECTS): CFLAGS := $(filter-out -mthumb -O2,$(CFLAGS)) -marm -O3 -fomit-frame-pointer

$(BUILD)/vmskel_05_printf.o: CFLAGS += -DKVM_STDIO_IMPLEMENTATION=1

$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD) $(TARGET).nds unprepared.nds

env:
	@echo "TARGET=$(TARGET)"
	@echo "EMBEDDED_SCRATCHPAD=$(EMBEDDED_SCRATCHPAD)"
	@echo "CC=$(CC)"
