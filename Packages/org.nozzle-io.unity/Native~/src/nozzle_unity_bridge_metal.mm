#include "IUnityGraphics.h"
#include "IUnityGraphicsMetal.h"
#include "IUnityInterface.h"

extern "C" void *nozzle_unity_environment_get_metal_device(IUnityInterfaces *unity_interfaces) {
    if(unity_interfaces == nullptr) {
        return nullptr;
    }

    IUnityGraphicsMetalV2 *metal_v2 = unity_interfaces->Get<IUnityGraphicsMetalV2>();
    if(metal_v2 != nullptr && metal_v2->MetalDevice != nullptr) {
        return (__bridge void *)metal_v2->MetalDevice();
    }

    IUnityGraphicsMetalV1 *metal_v1 = unity_interfaces->Get<IUnityGraphicsMetalV1>();
    if(metal_v1 != nullptr && metal_v1->MetalDevice != nullptr) {
        return (__bridge void *)metal_v1->MetalDevice();
    }

    IUnityGraphicsMetal *metal = unity_interfaces->Get<IUnityGraphicsMetal>();
    if(metal != nullptr && metal->MetalDevice != nullptr) {
        return (__bridge void *)metal->MetalDevice();
    }

    return nullptr;
}
