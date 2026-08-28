# Starred player UI

Available ranked-player cards expose a star control. Selecting it highlights that card as a personal target. Star state is stored in browser `localStorage` by Sleeper player id, so it survives automatic board refreshes and page reloads on the same browser.

Starring is presentation-only. It must not change board ordering, plan criteria, Cost of Waiting, positional strength, or server state.
