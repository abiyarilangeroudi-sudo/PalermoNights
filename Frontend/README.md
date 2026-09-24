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

## Planned application surfaces

1. Lobby and player/provider assignment.
2. Private role reveal.
3. Discussion table with ordered speakers, questions, answers, and claims.
4. Voting panel with Vote, Suspect #2, Trusted Player, and private Trust values.
5. Role-specific night action panel.
6. Morning newspaper result, elimination reveal, will, and game-over screen.

The browser should consume only player-scoped API responses. Provider credentials remain server-side.
