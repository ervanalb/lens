TARGET = clens
CC = gcc

# Source files
C_SRC  = $(wildcard *.c)

OBJDIR = build
$(shell mkdir -p $(OBJDIR) >/dev/null)
OBJECTS = $(C_SRC:%.c=$(OBJDIR)/%.o)

# Compiler flags
INC = -I.

LIBRARIES = 

CFLAGS = -std=c99 -ggdb3 -Og 
CFLAGS += $(INC)
CFLAGS += -Wall -Wextra -Werror -Wno-unused-parameter
CFLAGS += -D_POSIX_C_SOURCE=20160619
LFLAGS = $(CFLAGS)

# File dependency generation
DEPDIR = .deps
$(shell mkdir -p $(DEPDIR) >/dev/null)
DEPS = $(OBJECTS:$(OBJDIR)/%.o=$(DEPDIR)/%.d)
-include $(DEPS)
$(DEPDIR)/%.d : %.c .deps
	@mkdir -p $(dir $@)
	@$(CC) $(CFLAGS) $< -MM -MT $(@:$(DEPDIR)/%.d=%.o) >$@

# Targets
$(TARGET): $(OBJECTS) libdill/ibdill.la
	$(CC) $(LFLAGS) -o $@ $< $(LIBRARIES)

$(OBJDIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(APP_INC) -c -o $@ $<

libdill/ibdill.la:
	$(MAKE) -C libdill

.PHONY: all
all: $(TARGET)

.PHONY: clean
clean:
	-rm -f $(TARGET) tags
	-rm -rf $(OBJDIR) $(DEPDIR)

tags: $(C_SRC)
	ctags -R .

.DEFAULT_GOAL := all
