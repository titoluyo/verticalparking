idf_component_register(
  INCLUDE_DIRS "detail/fmt/include" "include")

target_compile_options(${COMPONENT_LIB} INTERFACE "-Wno-error=tautological-compare")
