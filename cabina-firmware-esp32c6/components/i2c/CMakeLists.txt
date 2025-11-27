idf_component_register(
  INCLUDE_DIRS "include"
  SRC_DIRS "src"
  REQUIRES "driver" "base_component" "cli" "task")

target_compile_options(${COMPONENT_LIB} PRIVATE "-Wno-error=tautological-compare")
