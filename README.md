# Battleship Tournament

Oceania is at war with Eurasia. Oceania has always been at war with Eurasia.
The Ministry of Peace has recruited you to help the navy, and what the navy
needs is code.

You are going to write a small Python strategy that plays Battleship, and then
every strategy in the class plays every other strategy. The strategies that
finish in the top **three** each win a duck.

There is one catch: the unchanged `demo_strategy.py` plays in the tournament
too, as the **baseline**. To win a duck you must be in the top three **and**
finish above it.

## The game

Each player has a 10 × 10 board with five ships hidden on it. The ships are
5, 4, 3, 3 and 2 squares long. They lie in a straight line, across or down,
and never overlap (they are allowed to touch).

The players take turns to shoot at one square of the other player's board.
After each shot you are told whether it was a **miss** or a **hit**, and when
every square of a ship has been hit you are told that the ship is **sunk**.
The first player to sink all five enemy ships wins.

Your code is the one deciding where to shoot. A good strategy needs fewer
shots to find and sink everything.

## The tournament

- You play ten games against every other strategy, and take turns to go first.
- Ships are in different places every game.
- The winner is the strategy with the best win percentage. Ties go to whoever
  needs fewer shots, on average, to win.

## How to enter

1. Download this project: on GitHub click the green **Code** button, then
   **Download ZIP**, and unzip it.
2. Open `strategies/demo_strategy.py`. Everything you need is in that one file.
3. Change `strategy_name = 'Demo Strategy'` to your name or team name.
4. Replace the code inside `take_shot()` with your own idea.
5. Rename the file to something else ending in `.py`, such as `maria_and_sam.py`.
6. Upload that one file to the assignment.

You must change **both** the name inside the file and the name of the file.
A renamed file that still says `'Demo Strategy'`, or a file still called
`demo_strategy.py` with a new name inside, will not be allowed to play. Two
entries with the same `strategy_name` will not be allowed to play either.

## Writing your strategy

Your file needs a function called `take_shot`. It is called every time it is
your turn, and it must return the square you want to shoot at as
`(row, column)`:

```python
def take_shot(board, ships_left):
    for row in range(10):
        for column in range(10):
            if board[row][column] == '.':     # not tried yet
                return (row, column)
```

Rows and columns are both numbered **0 to 9**. `(0, 0)` is the top left corner
and `(0, 9)` is the top right.

| You are given | What it is                                                         |
|---------------|--------------------------------------------------------------------|
| `board`       | What you know so far about the board you are shooting at           |
| `ships_left`  | The lengths of the enemy ships you have not sunk yet, e.g. `[5, 3, 2]` |

`board[row][column]` is one of four letters:

| Letter | Meaning                                                    |
|--------|------------------------------------------------------------|
| `'.'`  | You have not shot here yet                                 |
| `'M'`  | You shot here and **missed**                               |
| `'H'`  | You shot here and **hit** a ship that is still afloat      |
| `'S'`  | You shot here, and that ship has now been **sunk**         |

If your code crashes, shoots off the board, or shoots at a square it has
already tried, **your turn is wasted** and the other player shoots next.

### Where to start

The demo strategy shoots at random. It is weak for two reasons, and each one is
a good place to start:

1. **Searching.** Random shots waste a lot of turns. The smallest ship is two
   squares long, so do you really need to try every square to find it?
2. **After a hit.** The demo does nothing different when it hits a ship. But if
   a square is `'H'`, the rest of that ship must be right next to it. Where
   should the next shot go? And once you have two hits in a line?

The `examples` folder has four opponents you can play against. The first three
do nothing different after a hit, so you can beat them all. The fourth is much
tougher, and how it works is a secret:

| Name        | What it does                                                        |
|-------------|---------------------------------------------------------------------|
| `rando`     | Shoots at random squares                                            |
| `checkers`  | Shoots at every second square, like one colour of a checkerboard    |
| `recursion` | Shoots at the middle of the board, then the middle of each quarter, then each quarter of those, and so on |
| `secret`    | That would be telling. Can you beat it? Can you work out what it does by watching it play? |

There is one more opponent. Mr. Bartucz has a secret strategy of his own, which
won a previous tournament. He will reveal it on Monday.

### Placing your own ships (optional)

If you do nothing, your ships are placed at random every game. To choose where
they go, add a `place_ships` function. There is an example at the bottom of
`demo_strategy.py` with instructions.

## Testing your strategy

Run your own file to check that it returns sensible shots:

```
python strategies/maria_and_sam.py
```

Then start the tournament program:

```
python run_tournament.py
```

It checks the files and gives you three choices:

1. **Play one-v-one.** Pick any two strategies from a numbered list and watch
   them play with both boards on screen. A strategy can play against itself.
2. **Play an entire tournament** against the demo and all the examples.
3. **Exit.**

You can also skip the choices and go straight to one game against an example:

```
python run_tournament.py --versus rando
```

Each board shows one player's shots. You can see the ships that have not been
hit yet, so you can watch your strategy just miss them. Some useful extras:

| Command                                              | What it does                              |
|------------------------------------------------------|-------------------------------------------|
| `python run_tournament.py --versus rando --speed 3`  | Slower: 3 shots a second (the default is 10) |
| `python run_tournament.py --versus rando --speed 0`  | As fast as possible                       |
| `python run_tournament.py --versus rando --games 20` | A series of 20 games                      |
| `python run_tournament.py --versus rando checkers`   | Any two strategies, by name               |

If something is wrong with your file, the tournament tells you what before it
starts. Afterwards it lists any wasted shots, and `results.txt` has the full
results.

Use a real terminal window for the coloured boards. Some editors' output
panels can't show them, and you will get a plain list of results instead.

## Rules

- Your strategy may only use the things its functions are given. It may not
  read or change other files, other strategies, or the tournament program.
- `import random` is fine. Don't use anything that needs to be installed.
- Keep it quick: no waiting, no asking for input, no loops that never end.
  A file that runs for more than five seconds in the pre-start check is left out.

---

## For the teacher

Download the students' files from the LMS and drop them all into the
`strategies` folder. The file names don't matter. Then:

| Command                                          | What it does                                         |
|--------------------------------------------------|------------------------------------------------------|
| `python run_tournament.py --check --no-examples` | Checks every file and lists problems, without playing |
| `python run_tournament.py --no-examples`         | The real tournament: only the `strategies` folder        |
| `python run_tournament.py --no-examples --seconds 120` | Same, with the leaderboard stretched to about two minutes |
| `python run_tournament.py --no-examples --watch` | Same, showing both boards for every game             |
| `python run_tournament.py --versus "Name" "Other Name"` | One game between two named strategies         |
| `python run_tournament.py`                       | Practice: `strategies` plus `examples`, starting with the choice of one-v-one or a tournament |

- `--watch` shows every shot of every game, so it is slow: thirty students is
  4,350 games. Use `--speed 0` for the fastest display, or `--games 2` for a
  shorter tournament. A good show is the normal tournament first, then
  `--versus` for the final between the top two.
- Files with problems (syntax errors, endless loops, a missing `take_shot`,
  missing or duplicate `strategy_name`, the demo name/filename rule) are listed
  before the start and left out. Fix them and run again, or press Enter to play
  without them.
- Leave `demo_strategy.py` in the `strategies` folder. It plays as the baseline,
  marked on the leaderboard, and the results end with the top three students
  who finished above it. If it is missing, no prize list is shown.
- `results.txt` is rewritten as the tournament runs and holds the leaderboard,
  a head-to-head table and any wasted shots. It is overwritten each run.
- If the tournament hangs anyway, press Ctrl+C: it reports which two files were
  playing and saves the results so far.
- The board size, the ships and the number of games per pair are at the top of
  `run_tournament.py`.
