PARAMS ?= params.json

generate:
	cd python && uv run python -m pll.generate --params ../$(PARAMS) --output ../generated

cpp-validate: generate
	$(MAKE) -C cpp
	./cpp/main

sim: generate
	$(MAKE) -C rtl icarus

all: generate cpp-validate sim

clean:
	rm -rf generated
	$(MAKE) -C cpp fclean
	$(MAKE) -C rtl clean

.PHONY: generate cpp-validate sim all clean
