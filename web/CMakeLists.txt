# Preklad jadra vAmiga do WebAssembly (Emscripten) + glue.
# Prevzato 2026-09-06 z projektu Turrican (../Turrican-projekt).
# Pouziti: tools/build-wasm.sh (klonuje jadro, aplikuje patche, vola emcmake).
cmake_minimum_required(VERSION 3.16)
project(vamiga_wasm CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)
if(NOT DEFINED VAMIGA_CORE)
  message(FATAL_ERROR "VAMIGA_CORE musi ukazovat na adresar Core jadra vAmiga")
endif()
add_definitions(-DNDEBUG)
add_compile_options(-O2 -fwasm-exceptions -sWASM_LEGACY_EXCEPTIONS=0 -mnontrapping-fptoint -sUSE_ZLIB=1 -Wno-unused-parameter)
add_subdirectory(${VAMIGA_CORE} VACore EXCLUDE_FROM_ALL)
add_executable(vamiga glue.cpp)
target_include_directories(vamiga PRIVATE ${VAMIGA_CORE} ${VAMIGA_CORE}/Infrastructure ${VAMIGA_CORE}/Components ${VAMIGA_CORE}/Components/Memory)
target_link_libraries(vamiga PRIVATE VACore)
target_link_options(vamiga PRIVATE
  -O2 -fwasm-exceptions -sWASM_LEGACY_EXCEPTIONS=0 -sUSE_ZLIB=1
  -sMODULARIZE=1 -sEXPORT_NAME=createVAmiga -sENVIRONMENT=web,worker,node
  -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=256MB -sTOTAL_STACK=16MB
  -sNO_EXIT_RUNTIME=1 -sASSERTIONS=0
  -sEXPORTED_RUNTIME_METHODS=cwrap,ccall,HEAPU8,HEAPU32,HEAPF32,UTF8ToString,stringToUTF8,lengthBytesUTF8
  -sEXPORTED_FUNCTIONS=_malloc,_free,_wasm_init,_wasm_error,_wasm_retroshell,_wasm_update,_wasm_load_rom,_wasm_insert_disk,_wasm_eject_disk,_wasm_power_on,_wasm_is_running,_wasm_step,_wasm_step_line,_wasm_frames,_wasm_retroshell_text,_wasm_agnus_frame,_wasm_chip_ptr,_wasm_chip_size,_wasm_slow_ptr,_wasm_slow_size,_wasm_texture_ptr,_wasm_texture_width,_wasm_texture_height,_wasm_audio_count,_wasm_audio_copy,_wasm_audio_left,_wasm_audio_right,_wasm_set_sample_rate,_wasm_joystick,_wasm_mouse,_wasm_key,_wasm_warp,_wasm_snapshot_take,_wasm_snapshot_size,_wasm_snapshot_load,_wasm_version
)
set_target_properties(vamiga PROPERTIES OUTPUT_NAME vamiga SUFFIX .js)
