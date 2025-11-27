idf_component_register(
  INCLUDE_DIRS "include"
  SRC_DIRS "src"
  REQUIRES base_component pthread)

target_compile_options(${COMPONENT_LIB} PRIVATE "-Wno-error=tautological-compare")
