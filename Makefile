# Makefile для сборки simple проекта под Nintendo Switch

# Путь к devkitPro (у тебя должен быть установлен)
PREFIX = aarch64-none-elf-
CC = $(PREFIX)gcc
CFLAGS = -Wall -O2 -ffunction-sections -fdata-sections -I$(DEVKITPRO)/libnx/include
LDFLAGS = -lnx -nostartfiles -Wl,--gc-sections

BUILD_DIR = build
TARGET = main
OUTPUT = $(TARGET).nro

SOURCES = main.c
OBJECTS = $(SOURCES:.c=.o)

all: $(BUILD_DIR)/$(OUTPUT)

$(BUILD_DIR)/$(OUTPUT): $(addprefix $(BUILD_DIR)/, $(OBJECTS))
	mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(addprefix $(BUILD_DIR)/, $(OBJECTS)) -o $@ $(LDFLAGS)

$(BUILD_DIR)/%.o: %.c
	mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all clean
