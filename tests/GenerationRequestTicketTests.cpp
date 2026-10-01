#include "generation/GenerationRequestTicket.h"

#include <cassert>

using namespace mozart::generation;

namespace {

void testTicketMatchesOnlyCurrentModel() {
    const GenerationRequestTicket ticket{"model-a"};

    assert(ticket.matches("model-a", 7));
    assert(!ticket.matches("model-a", 8));
    assert(!ticket.matches("model-b", 7));
    assert(!ticket.matches("", 7));
}

void testEmptyTicketNeverMatches() {
    const GenerationRequestTicket ticket{};

    assert(!ticket.matches("model-a", 1));
    assert(!ticket.matches("", 0));
}

} // namespace

int main() {
    testTicketMatchesOnlyCurrentModel();
    testEmptyTicketNeverMatches();
    return 0;
}
