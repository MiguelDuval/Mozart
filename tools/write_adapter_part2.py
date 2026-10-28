f = open('src/core/RemiEventAdapter.cpp', 'a')
f.write('''
std::optional<RemiEvent> RemiEventAdapter::parseTokenName(const std::string& tokenName) const noexcept {
    if (tokenName.empty()) return std::nullopt;
    if (tokenName == "PAD_None" || tokenName == "BOS_None" || tokenName == "EOS_None" || tokenName == "MASK_None") return std::nullopt;
    if (tokenName == "Bar_None") return RemiBarEvent{0};
    if (tokenName.rfind("Pitch_", 0) == 0) {
        std::string pitchStr = tokenName.substr(6);
        try {
            int pitch = std::stoi(pitchStr);
            if (pitch >= config_.pitchMin && pitch <= config_.pitchMax) {
                return RemiNoteOnEvent{static_cast<std::uint8_t>(pitch), 0, 0, 0};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("PitchDrum_", 0) == 0) {
        std::string pitchStr = tokenName.substr(10);
        try {
            int pitch = std::stoi(pitchStr);
            return RemiNoteOnEvent{static_cast<std::uint8_t>(pitch), 0, 0, 0};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Velocity_", 0) == 0) {
        std::string velStr = tokenName.substr(9);
        try {
            int bin = std::stoi(velStr);
            if (bin >= 0 && bin < config_.numVelocities) {
                return RemiVelocityEvent{static_cast<std::uint8_t>(velocityBinToMidi(static_cast<std::uint8_t>(bin)))};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Position_", 0) == 0) {
        std::string posStr = tokenName.substr(9);
        try {
            int bin = std::stoi(posStr);
            return RemiPositionEvent{positionBinToTicks(static_cast<std::uint32_t>(bin))};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Tempo_", 0) == 0) {
        std::string tempoStr = tokenName.substr(6);
        try {
            int bin = std::stoi(tempoStr);
            if (bin >= 0 && bin < config_.numTempos) {
                return RemiTempoEvent{tempoBinToBpm(static_cast<std::uint8_t>(bin))};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Program_", 0) == 0) {
        std::string progStr = tokenName.substr(8);
        try {
            int program = std::stoi(progStr);
            if (program >= -1 && program <= 127) {
                return RemiProgramEvent{static_cast<std::uint8_t>(program >= 0 ? program : 0), 0};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Chord_", 0) == 0) {
        std::string chordPart = tokenName.substr(6);
        size_t underscore = chordPart.find("_");
        if (underscore != std::string::npos) {
            std::string root = chordPart.substr(0, underscore);
            std::string quality = chordPart.substr(underscore + 1);
            return RemiChordEvent{root, quality};
        }
    }
    if (tokenName.rfind("TimeSig_", 0) == 0) {
        std::string tsPart = tokenName.substr(8);
        size_t underscore = tsPart.find("_");
        if (underscore != std::string::npos) {
            try {
                int num = std::stoi(tsPart.substr(0, underscore));
                int den = std::stoi(tsPart.substr(underscore + 1));
                if (num > 0 && den > 0) {
                    return RemiTimeSignatureEvent{static_cast<std::uint8_t>(num), static_cast<std::uint8_t>(den)};
                }
            } catch (...) { return std::nullopt; }
        }
    }
    return std::nullopt;
}

std::optional<RemiEvent> RemiEventAdapter::tokenNameToEvent(const std::string& tokenName) const noexcept {
    return parseTokenName(tokenName);
}
''')
f.close()
print('Part 2 done')