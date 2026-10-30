// A guard page immediately after the real legacy engine table catches even
// a one-pointer over-read in the client initialization copy.
#include <cassert>
#include <cstddef>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>

#include "../cl_dll/cl_dll.h"
#include "legacy_client_api.h"

int main()
{
	const auto page = static_cast<std::size_t>(sysconf(_SC_PAGESIZE));
	const auto legacySize = offsetof(cl_enginefunc_t, pfnFilteredClientCmd);
	static_assert(offsetof(cl_enginefunc_t, pfnVguiWrap2_GetMouseDelta) + sizeof(void*) == legacySize);
	assert(legacySize < page);
	void* memory = mmap(nullptr, page * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	assert(memory != MAP_FAILED);
	assert(mprotect(static_cast<char*>(memory) + page, page, PROT_NONE) == 0);
	auto* source = reinterpret_cast<cl_enginefunc_t*>(static_cast<char*>(memory) + page - legacySize);
	std::memset(source, 0x5a, legacySize);
	cl_enginefunc_t destination{};
	CopyLegacyClientEngineFunctions(destination, source);
	assert(std::memcmp(source, &destination, legacySize) == 0);
	assert(destination.pfnFilteredClientCmd == nullptr);
	assert(munmap(memory, page * 2) == 0);
}
