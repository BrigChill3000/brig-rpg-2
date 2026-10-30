#pragma once

#include <cstddef>
#include <cstring>

// The 25th-anniversary SDK appended this callback to the frozen engine API.
// steam_legacy only provides the prefix ending in pfnCheckParm.
inline void CopyLegacyServerEngineFunctions(enginefuncs_t& destination, const enginefuncs_t* source)
{
	destination = {};
	std::memcpy(&destination, source, offsetof(enginefuncs_t, pfnPEntityOfEntIndexAllEntities));
}
