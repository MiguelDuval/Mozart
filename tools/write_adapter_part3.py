f = open('src/core/RemiEventAdapter.cpp', 'a')
f.write('''
std::pair<PatternProposal, RemiDecodeReport> RemiEventAdapter::decodeTokensToProposal(
    const std::vector<std::uint32_t>& tokenIds,
    const GenerationRequest& request,
    const std::string& providerId,
    const std::string& modelId) const noexcept {
    auto startTime = std::chrono::high_resolution_clock::now();
    DecodeState state;
    RemiDecodeReport report;
    report.result = RemiDecodeResult::Ok;
    if (tokenIds.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "Empty token sequence";
        return {PatternProposal{}, report};
    }
    if (!tokenizer_) {
        report.result = RemiDecodeResult::InvalidToken;
        report.message = "No BPE tokenizer loaded.";
        return {PatternProposal{}, report};
    }
    std::vector<std::string> tokenNames = tokenizer_->decodeTokens(tokenIds);
    if (tokenNames.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "No valid tokens after BPE decoding";
        return {PatternProposal{}, report};
    }
    std::vector<RemiEvent> remiEvents;
    remiEvents.reserve(tokenNames.size());
    for (const auto& tokenName : tokenNames) {
        auto event = parseTokenName(tokenName);
        if (event.has_value()) {
            remiEvents.push_back(*event);
        } else {
            state.warnings.push_back("Unknown token: " + tokenName);
            state.droppedTokens++;
        }
    }
    auto result = decodeEventsToProposal(remiEvents, request, providerId, modelId);
    auto endTime = std::chrono::high_resolution_clock::now();
    auto generationTime = std::chrono::duration_cast<std::chrono::nanoseconds>(endTime - startTime);
    result.first.generationTime = generationTime;
    report.warnings.insert(report.warnings.end(), state.warnings.begin(), state.warnings.end());
    report.droppedTokens += state.droppedTokens;
    return result;
}

} // namespace mozart::generation
''')
f.close()
print('Part 3 done')