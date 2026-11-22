# An example strategy. Read it for ideas, but write your own in the
# "strategies" folder (start from strategies/demo_strategy.py).

strategy_name = 'checkers'

# Shoots at every second square, like the dark squares of a checkerboard.
# Every ship is at least 2 squares long, so every ship must be sitting on at
# least one dark square: after 50 shots it has hit all of them at least once.
# Only then does it go back and shoot at the light squares.
#
# It never changes what it does after a hit, so it is slow to finish ships off.


def take_shot(board, ships_left):
    # First the "dark" squares: the ones where row + column is an even number.
    for row in range(10):
        for column in range(10):
            if (row + column) % 2 == 0 and board[row][column] == '.':
                return (row, column)

    # The dark squares are all used up, so now any square that is left.
    for row in range(10):
        for column in range(10):
            if board[row][column] == '.':
                return (row, column)
