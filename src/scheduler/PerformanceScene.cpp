#include "PerformanceScene.h"

namespace mozart::scheduler {

PerformanceScene PerformanceScene::preset(
        const std::uint8_t index) noexcept {
    PerformanceScene scene;
    scene.index = static_cast<std::uint8_t>(index % kSceneCount);

    switch (scene.index) {
        case 1:
            scene.role = AccompanimentRole::Arpeggio;
            scene.density = generation::PatternDensity::Normal;
            scene.accent = generation::PatternAccent::Mild;
            scene.swing = generation::PatternSwing::Off;
            scene.seed = 0xA17E42B1u;
            break;
        case 2:
            scene.role = AccompanimentRole::Bass;
            scene.density = generation::PatternDensity::Sparse;
            scene.accent = generation::PatternAccent::Strong;
            scene.swing = generation::PatternSwing::Light;
            scene.seed = 0x7EED1234u;
            break;
        case 3:
            scene.role = AccompanimentRole::Arpeggio;
            scene.density = generation::PatternDensity::Full;
            scene.accent = generation::PatternAccent::Strong;
            scene.swing = generation::PatternSwing::Full;
            scene.seed = 0xC0DECAFEu;
            break;
        case 0:
        default:
            scene.role = AccompanimentRole::Bass;
            scene.density = generation::PatternDensity::Full;
            scene.accent = generation::PatternAccent::Off;
            scene.swing = generation::PatternSwing::Off;
            scene.seed = 0x4D4F5A41u;
            break;
    }

    return scene;
}

} // namespace mozart::scheduler
