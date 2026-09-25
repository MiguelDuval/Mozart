#include <jni.h>

#include "core/MozartEngine.h"

extern "C" JNIEXPORT jstring JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeEngineInfo(
        JNIEnv* env,
        jobject) {
    const mozart::MozartEngine engine;
    const auto info = engine.info();

    return env->NewStringUTF(info.c_str());
}
