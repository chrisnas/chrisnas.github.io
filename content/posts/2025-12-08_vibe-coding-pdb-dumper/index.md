---
title: "Vibe coding a .pdb dumper or how I became a Product Manager"
date: 2025-12-08T10:12:16.860Z
description: "Follow me Vibe Coding in Cursor during my Datadog R&D Week to list function symbols with their signature and more"
tags: ["C++", "performance", "diagnostics", "PDB", "DbgHelp", "Cursor"]
draft: false
cover:
  image: "1_sSP8l9m3GJ4PDA3FPRywww.png"
  relative: true
---

---

During this R&D week at Datadog, I wanted to implement a tool accepting a .pdb file and generate a .sym file listing functions symbols with their address, size, name with signature and if they are public or private. This post dig into the implementation details of using [Microsoft Debug Interface Access (DIA) COM API](https://learn.microsoft.com/en-us/visualstudio/debugger/debug-interface-access/getting-started-debug-interface-access-sdk??WT.mc_id=DT-MVP-5003325) to achieve these objectives. If you want to see what my vibe coding experience in Cursor was, read [this other post](/posts/2025-12-08_vibe-coding-pdb-dumper/) instead.

## One self-contained tool please!

I would like the tool to be self-contained but since DIA is based on a COM server, it would require registering msdia40.dll on the machine. Not a good idea. In case the dll is in the same folder as the tool, one could “emulate” the magic done by **CoCreateInstance** to get an instance of **IDiaDataSource** (more on this interface soon) by:

- Call **LoadLibrary** to load the dll in memory
- Call **GetProcAddress** to get the **DllGetClassObject** implementation
- Call this function to get the **IClassFactory** implementation
- Call its **CreateInstance** method to get an object implementing **IDiaDataSource**

Here is the corresponding code (without error checking for readability)

```cpp
// Create DIA data source without registration using DLL loading
HRESULT PdbSymbolExtractor::NoRegCoCreate(const std::wstring& dllPath, REFCLSID rclsid, REFIID riid, void** ppv) {
    HMODULE hDll = LoadLibraryW(dllPath.c_str());

    typedef HRESULT(__stdcall* DllGetClassObjectFunc)(REFCLSID, REFIID, LPVOID*);
    DllGetClassObjectFunc pDllGetClassObject = (DllGetClassObjectFunc)GetProcAddress(hDll, "DllGetClassObject");

    CComPtr<IClassFactory> pClassFactory;
    HRESULT hr = pDllGetClassObject(rclsid, IID_IClassFactory, (void**)&pClassFactory);

    hr = pClassFactory->CreateInstance(NULL, riid, ppv);

    // Note: We intentionally don't call FreeLibrary here because the DLL needs to stay loaded
    // The COM object references will keep it alive
    return S_OK;
```

This function is called with the path of msdia40.dll and the UUID of the expected **IDiaDataSource**:

```objectivec
// Create DIA data source without registration
hr = NoRegCoCreate(dllPath, CLSID_DiaSource, __uuidof(IDiaDataSource), (void**)&_pDiaDataSource);
```

But still, I don’t want to have two binaries!

The trick is to embed the msdia40.dll inside the tool as a Windows resource. In the .rc file, add an RCDATA entry that points to the dll:

```cpp
IDR_MSDIA_DLL      RCDATA      "x64\\Release\\msdia140.dll"
```

You should see it in the Resource View in Visual Studio:

![](1_-GYj2ovADruJxXqRMF930A.png)

Here is the code that extracts it as a file on disk is straightforward (error checking has been removed for readability):

```php
// Extract embedded msdia140.dll from resources
bool PdbSymbolExtractor::ExtractEmbeddedDll(const std::wstring& outputPath) {
    // Find the resource
    HMODULE hModule = GetModuleHandle(NULL);
    HRSRC hResource = FindResource(hModule, MAKEINTRESOURCE(IDR_MSDIA_DLL), RT_RCDATA);

    // Load the resource
    HGLOBAL hLoadedResource = LoadResource(hModule, hResource);

    // Lock the resource to get a pointer to the data
    LPVOID pResourceData = LockResource(hLoadedResource);

    // Get the size of the resource
    DWORD resourceSize = SizeofResource(hModule, hResource);

    // Write the DLL to disk
    std::ofstream outFile(outputPath, std::ios::binary);
    outFile.write(static_cast<const char*>(pResourceData), resourceSize);
    outFile.close();

    return true;
}
```

## Where are my function symbols?

After calling **NoRegCoCreate()**, _**pDiaDataSource** stores a reference to the entry point into the DIA APIs. Here are the steps to follow before being able to list the symbols:

```cpp
HRESULT PdbSymbolExtractor::ExtractSymbolsFromPdb(const std::wstring& pdbPath, std::vector<FunctionSymbol>& symbols) 
{
    // Load the PDB file
    HRESULT hr = _pDiaDataSource->loadDataFromPdb(pdbPath.c_str());

    // Open a session
    CComPtr<IDiaSession> pSession;
    hr = _pDiaDataSource->openSession(&pSession);

    // Get the global scope
    CComPtr<IDiaSymbol> pGlobal;
    hr = pSession->get_globalScope(&pGlobal);
```

Now, you have the global scope of the symbols, you can ask for an enumerator for the type of symbols you are interested in; **SymTagFunction** in my case:

```cpp
// Enumerate all function symbols
    CComPtr<IDiaEnumSymbols> pEnumSymbols;
    hr = pGlobal->findChildren(SymTagFunction, NULL, nsNone, &pEnumSymbols);

    LONG count = 0;
    pEnumSymbols->get_Count(&count);
    std::wcout << L"Found " << count << L" function symbols" << std::endl;
```

The **pEnumSymbols** iterator allows you to loop on each **SymTagFunction** symbol and get its name:

```cpp
while (SUCCEEDED(pEnumSymbols->Next(1, &pSymbol, &celt)) && celt == 1) {
        FunctionSymbol func;

        // Get function name
        BSTR bstrName;
        if (pSymbol->get_name(&bstrName) == S_OK) {
            func.name = bstrName;
            SysFreeString(bstrName);
        }
```

Note that each symbol details are stored in a **FunctionSymbol** instance:

```cpp
struct FunctionSymbol {
    std::wstring name;
    ...
    std::wstring signature; // Function signature (parameters only, no return type)
    DWORD rva;              // Relative Virtual Address
    ULONGLONG length;
    bool isPublic;
};
```

with the rest of the code in the **while()** loop:

```cpp
// Get function signature (parameters only, no return type)
    func.signature = ExtractFunctionSignature(pSymbol);

    // Get relative virtual address
    DWORD rva;
    if (pSymbol->get_relativeVirtualAddress(&rva) == S_OK) {
        func.rva = rva;
    }

    // Get function length
    ULONGLONG length;
    if (pSymbol->get_length(&length) == S_OK) {
        func.length = length;
    }

    // Determine if function is public or private
    // Check access level - default to private
    func.isPublic = false;
    DWORD access;
    if (pSymbol->get_access(&access) == S_OK) {
        func.isPublic = (access == CV_public);
    }

    pSymbol.Release();
```

I did not have the time to do more trial for private/public state, but I should have tried by enumerating **SymTagPublicSymbol** or **SymTagExport** that could be considered as public.

## Better with a signature

The final step is to figure out the signature of each function. This is where the genericity of DIA could be confusing because so many things are represented by **IDiaSymbol**: a symbol, a function, the type of a function, or the type of a parameter…

So, the type of the function is retrieved as an **IDiaSymbol** by calling **getType()** on the function symbol. From that **IDiaSymbol**, **findChildren()** lets you iterate on the parameters:

```cpp
// Extract function signature (parameters only, no return type)
std::wstring PdbSymbolExtractor::ExtractFunctionSignature(IDiaSymbol* pSymbol) {
    if (!pSymbol) {
        return L"()";
    }

    // Get function type
    CComPtr<IDiaSymbol> pFunctionType;
    if (pSymbol->get_type(&pFunctionType) != S_OK || !pFunctionType) {
        return L"()";
    }

    // Enumerate function arguments
    CComPtr<IDiaEnumSymbols> pEnumArgs;
    if (FAILED(pFunctionType->findChildren(SymTagFunctionArgType, NULL, nsNone, &pEnumArgs))) {
        return L"()";
    }

    LONG argCount = 0;
    pEnumArgs->get_Count(&argCount);

    if (argCount == 0) {
        return L"()";
    }
```

Now, the same **Next()** method is called on the enumerator to iterate on each parameter:

```cpp
// Build signature string
    std::wstring signature = L"(";
    CComPtr<IDiaSymbol> pArg;
    ULONG argCelt = 0;
    bool first = true;

    while (SUCCEEDED(pEnumArgs->Next(1, &pArg, &argCelt)) && argCelt == 1) {
        if (!first) {
            signature += L", ";
        }
        first = false;

        // Get the argument type
        CComPtr<IDiaSymbol> pArgType;
        if (pArg->get_type(&pArgType) == S_OK && pArgType) {
            signature += GetTypeName(pArgType);
        } else {
            signature += L"?";
        }

        pArg.Release();
    }

    signature += L")";
    return signature;
}
```

The final step is to get the name of the type from the **IDiaSymbol** returned by **get_type()**. If it is a custom type, call **get_name()** like any other symbol. Otherwise, for basic types, call **get_baseType()** and **get_length()** as shown by the code below:

```cpp
std::wstring PdbSymbolExtractor::GetTypeName(IDiaSymbol* pType) {
    if (!pType) {
        return L"?";
    }

    // Try to get type name directly
    BSTR bstrTypeName;
    if (pType->get_name(&bstrTypeName) == S_OK && bstrTypeName && wcslen(bstrTypeName) > 0) {
        std::wstring typeName = bstrTypeName;
        SysFreeString(bstrTypeName);
        return typeName;
    }

    // For basic types or unnamed types, try getting basic type info
    DWORD baseType = 0;
    ULONGLONG length = 0;

    if (pType->get_baseType(&baseType) == S_OK) {
        pType->get_length(&length);

        // Map basic types to names
        switch (baseType) {
            case btVoid: return L"void";
            case btChar: return L"char";
            case btWChar: return L"wchar_t";
            case btBool: return L"bool";

            case btInt:
            case btLong:
                if (length == 1) return L"char";
                else if (length == 2) return L"short";
                else if (length == 4) return L"int";
                else if (length == 8) return L"__int64";
                else return L"int" + std::to_wstring(length * 8);

            case btUInt:
            case btULong:
                if (length == 1) return L"unsigned char";
                else if (length == 2) return L"unsigned short";
                else if (length == 4) return L"unsigned int";
                else if (length == 8) return L"unsigned __int64";
                else return L"uint" + std::to_wstring(length * 8);

            case btFloat:
                if (length == 4) return L"float";
                else if (length == 8) return L"double";
                else return L"float" + std::to_wstring(length * 8);

            default:
                return L"?";
        }
    }

    return L"?";
}
```

This is a “simple” implementation that does not take pointers, addresses, arrays, and more into account. For a more complete solution, I would recommend looking at the **PrintType()** implementation in the DIA2Dump code sample that is installed with Visual Studio.

I hope this will get your foot in the door of symbol parsing and make you want to dig further into DIA.

## References

- Corresponding source code is available in [my github repository](https://github.com/chrisnas/VibeCoding).
- Archived Microsoft [documentation/implementation of .pdb format](https://github.com/microsoft/microsoft-pdb/tree/master) including a [symbol dumper](https://github.com/microsoft/microsoft-pdb/tree/master/cvdump) code.
- [DIA2Dump](https://learn.microsoft.com/en-us/visualstudio/debugger/debug-interface-access/dia2dump-sample) Visual Studio code sample.
