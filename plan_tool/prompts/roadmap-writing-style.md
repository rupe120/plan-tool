Short, plain, present tense. Everyday words, one idea per sentence, no filler.

**Open each paragraph with the point.** Say what it settles first, then the
reason. A reader who stops after the first sentence of each paragraph should
still know the outcome.

**The test: would a person say this to another person?** Read each line back as
if you were explaining it out loud to whoever has to apply it. If it is not
something a person would say, rewrite it. This governs every line of prose you
write, including the `chosen_option` and `rationale` of every decision.

Four things fail that test, and all four are easy to write without noticing.
The examples come from a library-lending domain; apply the same checks to
whatever domain you are writing about:

- **Invented words.** "No *unlapsed* reservation" — nobody says unlapsed. Say
  "a reservation that has not lapsed", or better, "while someone is waiting".
- **Records doing things.** A reservation does not *name* an item; a loan does
  not *carry a due at moment*. People do things and records hold what they did,
  so put the person back in the sentence.
- **Describing the table instead of the world.** "An item is on at most one
  open loan at any moment" is a row. "Only one member can have an item at a
  time" is the library.
- **Field names in prose.** Write "after the deadline", not "after the call's
  `deadline_at`". The inventory already carries the field name; the sentence is
  for a reader.

**Plain is not vague, and that is the trap here.** Every condition has to
survive the rewrite — "if someone is waiting", "or anything that would let them
work it out", "and nobody can wave it through". A sentence that reads nicely
and quietly dropped a condition is worse than the awkward one it replaced. Two
short sentences beat one unsayable sentence that keeps every clause.

**Say what a thing is the first time you name it.** A bare id or a term of
art is not an explanation. Give its plain-words meaning in the same sentence
("`reservation`, the record saying a member is waiting for an item that is
out"), and prefer a word this artifact or the artifacts above it already
define. If you cannot define a word in a few plain words, pick a different
word.

**This governs prose, not ids.** An `id` is an identifier, not a sentence.
Keep it a short kebab-case slug carrying the kind prefix its collection
already uses, and leave it alone when you make the prose plainer. A
sentence-shaped id is also harder to quote back exactly from one stage to the
next, which is how a later stage ends up anchoring to an id that does not
exist.

**Split a sentence, never a rule.** If something will not fit one sayable
sentence, write two. Do not divide one rule into two rows to make each row
shorter — how many rules there are follows the domain, not the prose.
