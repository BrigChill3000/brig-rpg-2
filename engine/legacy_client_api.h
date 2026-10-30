#pragma once

#include <cstddef>
#include <cstring>

// steam_legacy ends at pfnVguiWrap2_GetMouseDelta. The anniversary SDK
// appends pfnFilteredClientCmd without changing CLDLL_INTERFACE_VERSION.
// Do not read that pointer from an engine which never allocated it.
inline void CopyLegacyClientEngineFunctions(cl_enginefunc_t& destination, const cl_enginefunc_t* source)
{
	destination = {};
	std::memcpy(&destination, source, offsetof(cl_enginefunc_t, pfnFilteredClientCmd));
}
