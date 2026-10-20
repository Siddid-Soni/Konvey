| `grid` | a table of cells; an image of numbers with a filter sliding over it | `rows`, `cols`, `values` (row by row: `"1,0;0,1"` or flat; `""` for a cell not filled yet), `highlight-rows="1"`, `highlight-cols="0,2"`, `mark="r,c"` (flag one cell), `window="r,c,h,w"` (a frame over h×w cells from row r, col c), `kernel="1,0,-1;1,0,-1;1,0,-1"` (the filter's weights, shown small in the window's cells), `heat="true"` (cells coloured by value; or `"low,high"`), `row-labels="cat,dog,fox"` / `col-labels="said cat,said dog,said fox"` (names beside the rows, over the columns), `cells="dots"` (each number drawn as a dot sized by it: the pattern at a glance), `strike="below"` / `"above"` / `"0,1;2,3"` (cells crossed out: a mask, an impossible move), `sweep="columns"` / `"rows"` (this beat's new values arrive one column or row at a time under a moving frame), `op="softmax"` (the step's name, written by that frame), `look="matrix"` (a matrix: brackets, no cell boxes, spaced like a `vector`), `size` |

**A filter sliding over a grid** (`window`, `kernel`, `heat`): keep the grid's id, `values` and
`kernel` and change only `window` from beat to beat: between beats the frame steps cell by cell,
in reading order, to its new place (from `"0,2,3,3"` to `"1,1,3,3"` it visits `1,0` then `1,1`),
so one beat may cover a few steps (give it `t="3"`). The result is a second grid beside it whose
cells start empty (`""`) and get one value per step: changed cells fill in one after another in
reading order, each with a short flash, in time with the window's steps (one new cell per step).
`heat="true"` colours numbers on one dark-to-accent ramp for the whole scene (negatives take a
second hue), so a filled map shows where values are high without a legend. 
**Named rows and columns** (`row-labels`, `col-labels`): a table about things, not positions: a
confusion matrix (rows actual, columns predicted), a truth table, a distance table, how much each
word attends to each word (the same names on both). Keep the id and change the other attributes
beat by beat: `cells="dots"` turns the numbers into dots for the pattern and back; `strike` crosses
out cells one by one; a beat that changes many values with `sweep="columns"` (or `"rows"`) and
`op="…"` shows the step line by line (normalising each column, a softmax, dividing each row by its
total). Lit rows or columns (`highlight-rows`, `highlight-cols`) are the cells being read: a
number elsewhere (a `vector` entry, a label) that changes to one of their values flies out of
that cell.
