//
// QNN JNI bridge — loads a HTP v73 context binary and runs inference.
//
// This library is co-loaded with the bundled libQnnHtp.so (in jniLibs/arm64-v8a/).
// It uses dlopen / dlsym to resolve the QNN C API at runtime, so it works
// without compile-time headers and supports SDK version pinning.
//

#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <string>
#include <vector>

#define LOG_TAG "QnnLoaderJni"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ---------- QNN function pointer typedefs (subset of qnn_interface.h) ----------

// We resolve these via dlsym rather than including the header, so the SDK
// version is decoupled from the build.

// clang-format off
using QnnInterfaceGetProviders_t =
    int (*)(const void ***providerList, uint32_t *numProviders);
using QnnBackendCreate_t =
    int (*)(void **backendHandle, const void *sgw);
using QnnBackendFree_t =
    int (*)(void *backendHandle);
using QnnContextCreateFromBinary_t =
    int (*)(void *backendHandle, void **contextHandle,
            const void **config, const uint8_t *binary, uint32_t binarySize,
            uint32_t sgbwSize);
using QnnContextFree_t =
    int (*)(void *contextHandle, void *backendHandle);
using QnnGraphExecute_t =
    int (*)(void *contextHandle, void *graphHandle,
            const void *inputTensors, uint32_t numInputTensors,
            void *outputTensors, uint32_t numOutputTensors);
using QnnTensorCreateGraphTensors_t =
    int (*)(void *contextHandle, const void **graphs, uint32_t numGraphs,
            void **tensors, uint32_t *numTensors);
using QnnTensorGetData_t =
    int (*)(void *tensorHandle, uint8_t **data, uint32_t *dataSize);
// clang-format on

// ---------- Internal handle ----------

struct QnnHandle {
    void *qnnLib{nullptr};
    void *backendHandle{nullptr};
    void *contextHandle{nullptr};
    void *graphHandle{nullptr};

    // Resolved function pointers
    QnnBackendCreate_t backendCreate{nullptr};
    QnnBackendFree_t backendFree{nullptr};
    QnnContextCreateFromBinary_t contextCreateFromBinary{nullptr};
    QnnContextFree_t contextFree{nullptr};
    QnnGraphExecute_t graphExecute{nullptr};
    QnnTensorCreateGraphTensors_t tensorCreateGraphTensors{nullptr};
    QnnTensorGetData_t tensorGetData{nullptr};
};

// ---------- JNI helpers ----------

static jlong jniHandle(jlong handle) { return handle; }
static QnnHandle *fromJni(jlong handle) {
    return reinterpret_cast<QnnHandle *>(static_cast<intptr_t>(handle));
}

// ---------- JNI implementations ----------

extern "C" {

/**
 * Initialise the QNN HTP backend.
 *
 * Opens libQnnHtp.so via dlopen, resolves function pointers,
 * and calls QnnBackend_create.
 *
 * @return  Opaque handle (long) or 0 on failure.
 */
JNIEXPORT jlong JNICALL
Java_com_kavi_app_qnn_QnnModelLoader_nativeInit(JNIEnv *env, jobject /*thiz*/) {
    auto *h = new (std::nothrow) QnnHandle();
    if (!h) {
        LOGE("Failed to allocate QnnHandle");
        return 0L;
    }

    // 1. Open libQnnHtp.so
    h->qnnLib = dlopen("libQnnHtp.so", RTLD_NOW | RTLD_GLOBAL);
    if (!h->qnnLib) {
        LOGE("dlopen libQnnHtp.so failed: %s", dlerror());
        delete h;
        return 0L;
    }

    // 2. Resolve function pointers
    auto getProviders = reinterpret_cast<QnnInterfaceGetProviders_t>(
        dlsym(h->qnnLib, "QnnInterface_getProviders"));
    if (!getProviders) {
        LOGE("dlsym QnnInterface_getProviders failed: %s", dlerror());
        dlclose(h->qnnLib);
        delete h;
        return 0L;
    }

    const void **providerList = nullptr;
    uint32_t numProviders = 0;
    int rc = getProviders(&providerList, &numProviders);
    if (rc != 0 || numProviders == 0 || !providerList) {
        LOGE("QnnInterface_getProviders failed: rc=%d, num=%u", rc, numProviders);
        dlclose(h->qnnLib);
        delete h;
        return 0L;
    }

    // Use the first (and typically only) provider.
    // In QNN 2.31, the provider struct layout is:
    //   { apiVersion, backendCreate, backendFree, contextCreateFromBinary, ... }
    // We hardcode pointer offsets for the subset we need.
    // This is fragile across SDK versions — in production, parse the struct.
    auto **provider = reinterpret_cast<void **>(
        const_cast<void *>(providerList[0]));

    // Typical offset for QnnSBackend_Api_t (index 1):
    //   provider[0] = apiVersion
    //   provider[1] -> struct { create, free, ... }
    if (numProviders >= 1 && provider[1] != nullptr) {
        auto *backendApi = static_cast<void **>(provider[1]);
        // backendApi[0] = create, backendApi[1] = free
        h->backendCreate =
            reinterpret_cast<QnnBackendCreate_t>(backendApi[0]);
        h->backendFree =
            reinterpret_cast<QnnBackendFree_t>(backendApi[1]);
    }

    // Context API (might be at provider[2] depending on SDK struct layout).
    // Fallback: dlsym individual entry points directly.
    if (!h->backendCreate) {
        h->backendCreate =
            reinterpret_cast<QnnBackendCreate_t>(dlsym(h->qnnLib, "QnnBackend_create"));
    }
    if (!h->backendFree) {
        h->backendFree =
            reinterpret_cast<QnnBackendFree_t>(dlsym(h->qnnLib, "QnnBackend_free"));
    }
    h->contextCreateFromBinary =
        reinterpret_cast<QnnContextCreateFromBinary_t>(
            dlsym(h->qnnLib, "QnnContext_createFromBinary"));
    h->contextFree =
        reinterpret_cast<QnnContextFree_t>(dlsym(h->qnnLib, "QnnContext_free"));
    h->graphExecute =
        reinterpret_cast<QnnGraphExecute_t>(dlsym(h->qnnLib, "QnnGraph_execute"));
    h->tensorCreateGraphTensors =
        reinterpret_cast<QnnTensorCreateGraphTensors_t>(
            dlsym(h->qnnLib, "QnnTensor_createGraphTensors"));
    h->tensorGetData =
        reinterpret_cast<QnnTensorGetData_t>(dlsym(h->qnnLib, "QnnTensor_getData"));

    if (!h->backendCreate || !h->backendFree) {
        LOGE("Failed to resolve QnnBackend_create/free");
        dlclose(h->qnnLib);
        delete h;
        return 0L;
    }

    // 3. Create backend
    void *backendHandle = nullptr;
    rc = h->backendCreate(&backendHandle, nullptr);
    if (rc != 0 || !backendHandle) {
        LOGE("QnnBackend_create failed: rc=%d", rc);
        dlclose(h->qnnLib);
        delete h;
        return 0L;
    }
    h->backendHandle = backendHandle;

    LOGI("QNN HTP backend initialised (handle=%p)", h);
    return static_cast<jlong>(reinterpret_cast<intptr_t>(h));
}

/**
 * Load a context binary from file.
 */
JNIEXPORT jboolean JNICALL
Java_com_kavi_app_qnn_QnnModelLoader_nativeLoadContext(
    JNIEnv *env, jobject /*thiz*/, jlong handle, jstring binaryPath) {
    auto *h = fromJni(handle);
    if (!h || !h->backendHandle) {
        LOGE("nativeLoadContext: invalid handle");
        return JNI_FALSE;
    }
    if (!h->contextCreateFromBinary) {
        LOGE("nativeLoadContext: contextCreateFromBinary not resolved");
        return JNI_FALSE;
    }

    const char *path = env->GetStringUTFChars(binaryPath, nullptr);
    if (!path) return JNI_FALSE;

    // Read binary file into memory
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        LOGE("Cannot open context binary: %s", path);
        env->ReleaseStringUTFChars(binaryPath, path);
        return JNI_FALSE;
    }
    fseek(fp, 0, SEEK_END);
    long fileSize = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    auto *buffer = new (std::nothrow) uint8_t[fileSize];
    if (!buffer) {
        LOGE("Failed to allocate %ld bytes for context binary", fileSize);
        fclose(fp);
        env->ReleaseStringUTFChars(binaryPath, path);
        return JNI_FALSE;
    }
    size_t bytesRead = fread(buffer, 1, fileSize, fp);
    fclose(fp);
    if (static_cast<long>(bytesRead) != fileSize) {
        LOGE("Read %zu of %ld bytes from context binary", bytesRead, fileSize);
        delete[] buffer;
        env->ReleaseStringUTFChars(binaryPath, path);
        return JNI_FALSE;
    }

    void *contextHandle = nullptr;
    int rc = h->contextCreateFromBinary(
        h->backendHandle, &contextHandle, nullptr,
        buffer, static_cast<uint32_t>(fileSize), 0);

    delete[] buffer;
    env->ReleaseStringUTFChars(binaryPath, path);

    if (rc != 0 || !contextHandle) {
        LOGE("QnnContext_createFromBinary failed: rc=%d", rc);
        return JNI_FALSE;
    }
    h->contextHandle = contextHandle;

    // Discover graphs (usually one per context binary)
    if (h->tensorCreateGraphTensors) {
        // For a single-graph model, iterate graphs to find the first one
        // In production you'd enumerate graphs or use a known name
        h->graphHandle = contextHandle; // placeholder — will be set after graph enumeration
    }

    LOGI("Context binary loaded (%ld bytes)", fileSize);
    return JNI_TRUE;
}

/**
 * Execute inference on the loaded context binary.
 *
 * @return  Raw output tensor bytes.
 */
JNIEXPORT jbyteArray JNICALL
Java_com_kavi_app_qnn_QnnModelLoader_nativeExecute(
    JNIEnv *env, jobject /*thiz*/,
    jlong handle,
    jbyteArray inputTensor,
    jstring inputName,
    jstring outputName) {
    auto *h = fromJni(handle);
    if (!h || !h->contextHandle) {
        LOGE("nativeExecute: not initialised");
        return env->NewByteArray(0);
    }
    if (!h->graphExecute) {
        LOGE("nativeExecute: graphExecute not resolved");
        return env->NewByteArray(0);
    }

    // Allocate a reasonable output buffer (Whisper-Small encoder: 1500 floats = 6000 bytes)
    // In production this should be derived from the graph's output tensor shape.
    constexpr uint32_t kMaxOutputBytes = 64 * 1024;
    std::vector<uint8_t> outputBuffer(kMaxOutputBytes);

    // Build simple placeholder tensors.
    // Full implementation would:
    //   - Enumerate graph I/O tensors by name
    //   - Create Qnn_Tensor_t with correct rank/dimensions/type
    //   - Attach input data and output buffer
    //   - Call graphExecute
    //   - Read output tensor data
    //
    // For the v1 stub we copy the input through and produce dummy output
    // to validate the pipeline end-to-end.

    jsize inputLen = env->GetArrayLength(inputTensor);
    jbyte *inputBytes = env->GetByteArrayElements(inputTensor, nullptr);

    // Copy input as-is (placeholder: real impl forwards to QNN graph)
    const char *inName = env->GetStringUTFChars(inputName, nullptr);
    const char *outName = env->GetStringUTFChars(outputName, nullptr);
    LOGI("nativeExecute: input=%s (%d bytes) output=%s", inName, inputLen, outName);
    env->ReleaseStringUTFChars(inputName, inName);
    env->ReleaseStringUTFChars(outputName, outName);

    // Stub: fill output with zeros (real impl calls graphExecute)
    std::memset(outputBuffer.data(), 0, outputBuffer.size());

    env->ReleaseByteArrayElements(inputTensor, inputBytes, JNI_ABORT);

    jbyteArray result = env->NewByteArray(static_cast<jsize>(outputBuffer.size()));
    if (result) {
        env->SetByteArrayRegion(
            result, 0, static_cast<jsize>(outputBuffer.size()),
            reinterpret_cast<const jbyte *>(outputBuffer.data()));
    }
    return result;
}

/**
 * Shutdown: free context, free backend, close shared lib.
 */
JNIEXPORT void JNICALL
Java_com_kavi_app_qnn_QnnModelLoader_nativeShutdown(
    JNIEnv * /*env*/, jobject /*thiz*/, jlong handle) {
    auto *h = fromJni(handle);
    if (!h) return;

    if (h->contextHandle && h->contextFree) {
        h->contextFree(h->contextHandle, h->backendHandle);
        h->contextHandle = nullptr;
    }
    if (h->backendHandle && h->backendFree) {
        h->backendFree(h->backendHandle);
        h->backendHandle = nullptr;
    }
    if (h->qnnLib) {
        dlclose(h->qnnLib);
        h->qnnLib = nullptr;
    }
    delete h;
    LOGI("QNN backend shut down");
}

} // extern "C"