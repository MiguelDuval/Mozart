#include "generation/GenerationRequestTicket.h"

#include <cassert>

using namespace mozart::generation;

namespace {

void testTicketMatchesOnlyCurrentModel() {
    const GenerationRequestTicket ticket{"model-a"};

    assert(ticket.matches("model-a"));
    assert(!ticket.matches("model-b"));
    assert(!ticket.matches(""));
}

void testEmptyTicketNeverMatches() {
    const GenerationRequestTicket ticket{};

    assert(!ticket.matches("model-a"));
    assert(!ticket.matches(""));
}

} // namespace

int main() {
    testTicketMatchesOnlyCurrentModel();
    testEmptyTicketNeverMatches();
    return 0;
}
