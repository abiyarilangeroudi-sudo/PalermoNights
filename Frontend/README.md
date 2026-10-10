# Frontend visual direction

The supplied artwork establishes a portrait, noir-comic visual system. Character art is player identity only and must never imply or reveal an assigned role.

## Asset mapping

| Asset | UI use |
| --- | --- |
| `Character_1.jpeg` … `Character_7.jpeg` | Stable P1–P7 portraits and player cards |
| `Silhouettes_having_secret_conver.jpeg` | Night 1 Mafia strategy |
| `Silhouette_holding_handgun_in_alley.jpeg` | Mafia night action |
| `Detective_searching_dark_street.jpeg` | Detective investigation |
| `Doctor_protecting_patient.jpeg` | Doctor protection |
| `Person_reading_newspaper_in_city.jpeg` | Morning result |
| `Townspeople_voting_in_town_square.jpeg` | Discussion and voting |

All source images are `768×1376` portrait JPEGs. Keep these originals as source assets. Before a production UI build, generate responsive WebP/AVIF derivatives and thumbnails; the current source folder is approximately 10 MB.

## Implemented slide flow

1. Language and new-game landing screen.
2. Human character selection from seven portrait cards.
3. Private role reveal with character name and age.
4. Public claim selection: Citizen, Doctor, or Detective.
5. Seven-character claim reveal.
6. One speaker per discussion slide with typewriter dialogue.
7. Portrait-based human voting and a separate result slide.
8. Mafia target selection using the alley artwork.
9. Doctor protection using the hospital artwork.
10. Detective investigation using the dark-street artwork.
11. Citizen night watch using the secret-conversation artwork.
12. Morning news using the newspaper artwork.

The relevant role-specific night slide is shown to the human; the sequence repeats for later rounds until the game-over reveal.

The side journal has a visible-events tab and a personal-information tab. The latter contains registered role claims, citizen-team trust, role-specific investigations, and the selected Mafia scenario for Mafia players. The current player's name, portrait, and real role appear under the journal title. Human ASK/ANSWER and voting inputs collect the same required fields used by AI agents; a human Mafia Boss also selects the Night 1 strategy directly.

In the discussion and answer text field, typing `@` opens a portrait-and-name list of players. Further typing filters it; click a player or use the arrow keys and Enter to insert their full name at the caret.

Visible player names in scene text, questions, outcomes, and journal entries carry a small profile portrait, including Persian first-name references. Player selection menus in the discussion, vote form, and journal filter also show portraits beside each option.

The browser consumes only player-scoped API responses. A participant OpenAI key stays in tab memory, is sent only to the authenticated turn endpoint, and is cleared on reload, home, cancellation, or game over. It must never enter local storage or an archived report.
