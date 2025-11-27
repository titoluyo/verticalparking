idf_component_register(
  INCLUDE_DIRS "include"
  SRC_DIRS "src"
  REQUIRES base_component task)

target_compile_options(${COMPONENT_LIB} PRIVATE "-Wno-error=tautological-compare")
