# An example strategy. Read it for ideas, but write your own in the
# "strategies" folder (start from strategies/demo_strategy.py).

strategy_name = 'recursion'

# Cuts the board into quarters, again and again.
#
# It shoots at the middle of the whole board, then at the middle of each of
# the four quarters, then at the middle of each quarter of those quarters, and
# so on until the pieces are single squares. Its shots start spread far apart
# and slowly fill in the gaps.
#
# It never changes what it does after a hit, so it is slow to finish ships off.


def middles(top, left, height, width, depth):
    '''Return a list of (depth, row, column): the middle square of this piece
    of the board, and of every smaller piece it can be cut into.

    This function is "recursive": it calls itself on each of the four quarters.
    depth counts how many times the board has been cut to get to this piece.
    '''
    if height == 0 or width == 0:       # nothing here: this piece is empty
        return []

    found = [(depth, top + height // 2, left + width // 2)]
    if height == 1 and width == 1:      # a single square can't be cut any more
        return found

    half_height = height // 2
    half_width = width // 2
    found += middles(top, left, half_height, half_width, depth + 1)                             # top left
    found += middles(top, left + half_width, half_height, width - half_width, depth + 1)        # top right
    found += middles(top + half_height, left, height - half_height, half_width, depth + 1)      # bottom left
    found += middles(top + half_height, left + half_width,
                     height - half_height, width - half_width, depth + 1)                       # bottom right
    return found


# Work the order out once, when the file is loaded. sorted() puts the biggest
# pieces (the smallest depth) first.
SHOOTING_ORDER = []
for depth, row, column in sorted(middles(0, 0, 10, 10, 0)):
    if (row, column) not in SHOOTING_ORDER:
        SHOOTING_ORDER.append((row, column))


def take_shot(board, ships_left):
    for row, column in SHOOTING_ORDER:
        if board[row][column] == '.':
            return (row, column)
