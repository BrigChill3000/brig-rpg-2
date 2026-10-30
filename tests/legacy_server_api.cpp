#include <cassert>
#include <cstddef>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>

#include "extdll.h"
#include "legacy_server_api.h"

int main()
{
	const auto page = static_cast<std::size_t>(sysconf(_SC_PAGESIZE));
	const auto legacySize = offsetof(enginefuncs_t, pfnPEntityOfEntIndexAllEntities);
	static_assert(offsetof(enginefuncs_t, pfnCheckParm) + sizeof(void*) == legacySize);
	assert(legacySize < page);
	void* memory = mmap(nullptr, page * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	assert(memory != MAP_FAILED);
	assert(mprotect(static_cast<char*>(memory) + page, page, PROT_NONE) == 0);
	auto* source = reinterpret_cast<enginefuncs_t*>(static_cast<char*>(memory) + page - legacySize);
	std::memset(source, 0x5a, legacySize);
	enginefuncs_t destination{};
	CopyLegacyServerEngineFunctions(destination, source);
	assert(std::memcmp(source, &destination, legacySize) == 0);
	assert(destination.pfnPEntityOfEntIndexAllEntities == nullptr);
	assert(munmap(memory, page * 2) == 0);
}
