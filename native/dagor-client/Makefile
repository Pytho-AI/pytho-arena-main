CXX ?= clang++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -O2 -fobjc-arc
BUILD_DIR := build
TARGET := $(BUILD_DIR)/pytho-frame-receiver
TRANSFORM_TEST := $(BUILD_DIR)/enu-transform-test

.PHONY: all assets benchmark clean stage-assets test

all: $(TARGET)

$(TARGET): src/frame_receiver.mm
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $< -framework Foundation -o $@

$(TRANSFORM_TEST): tests/enu_transform_test.cpp src/enu_transform.hpp
	@mkdir -p $(BUILD_DIR)
	$(CXX) -std=c++17 -Wall -Wextra -Werror -O2 $< -o $@

test: $(TARGET) $(TRANSFORM_TEST)
	@actual="$$($(TARGET) < fixtures/frame-v1.ndjson)"; \
	expected="frame sequence=42 time=21.500 entities=2 active=1 tracks=1"; \
	test "$$actual" = "$$expected" || { echo "expected: $$expected"; echo "actual:   $$actual"; exit 1; }
	@actual="$$($(TARGET) < fixtures/frame-v1-ship.ndjson)"; \
	expected="frame sequence=0 time=0.000 entities=1 active=1 tracks=0"; \
	test "$$actual" = "$$expected" || { echo "expected: $$expected"; echo "actual:   $$actual"; exit 1; }
	@! printf '%s\n' '{"schemaVersion":2,"type":"frame"}' | $(TARGET) >/dev/null 2>&1
	@$(TRANSFORM_TEST)
	@echo "frame receiver tests passed"

benchmark: $(TARGET)
	node tools/benchmark_frame_receiver.mjs

assets:
	sh tools/build_pytho_assets.sh

stage-assets:
	sh tools/stage_pytho_viewer.sh

clean:
	rm -f $(TARGET) $(TRANSFORM_TEST)
