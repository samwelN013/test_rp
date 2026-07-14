# `__file__` paired with `pathlib`'s `.glob()` 

---

## 1. Absolute vs. Relative Paths (The `__file__` Difference)

The two paths you wrote do **not** always achieve the same result. The difference comes down to **where your script is located** versus **where you are running the script from**.

### Your Go-To Approach (Robust & Absolute)

```python
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'

```

* **`__file__`** is a special Python variable that holds the exact location of the current script file.
* **`.resolve()`** makes that path absolute (meaning it starts all the way from `C:/` or `/Users/`).
* **`.parent.parent`** climbs two folders up from where the script lives.
* **Why this is king:** It **never breaks**. No matter what folder your terminal is currently open in when you run the script, Python will always calculate the path relative to the *physical location of the script*.

### The Shorthand Approach (Fragile & Relative)

```python
folder = Path('./crypto_trades')  # or Path('crypto_trades')

```

* The `.` represents the **Current Working Directory (CWD)**—which is the folder your terminal/command prompt is currently sitting in when you type `python script.py`.
* **Why this can break:** If your terminal is open in `C:/Users/You` and your script is located in `C:/Users/You/Projects/Crypto`, Python will look for `./crypto_trades` in `C:/Users/You/crypto_trades` and crash because it can't find it.

> **The Verdict:** Only use `Path('./folder')` if you are 100% sure you will always run the script from the exact directory where that folder lives. Otherwise, stick to your `__file__` method—it is the industry gold standard for writing portable code.

---

## 2. What is `pathlib.Path` actually doing?

Historically, Python handled paths as raw strings (`os.path.join("folder", "subfolder")`).
`pathlib` changed the game by turning paths into **objects**.

When you write:

```python
folder / '_inputs' / 'crypto_trades'

```

You aren't just dividing strings. `pathlib` overrides Python's `/` division operator to act as a path joiner. It automatically handles slash directions for you:

* On **Windows**, it translates to `_inputs\crypto_trades`
* On **Mac/Linux**, it translates to `_inputs/crypto_trades`

No more manual string concatenation or worrying about operating systems.

---

## 3. How the `.glob()` method works

The word "glob" is short for *global*, originating from old Unix systems to mean "match a pattern of filenames."

In `pathlib`, `.glob()` is a method attached to a `Path` object. It searches the directory for files that match a pattern you give it, using **wildcards**:

* `*` means "match anything".
* `"*.csv"` means "find any file ending in `.csv`".
* `"*trade*"` means "find any file with the word 'trade' in its name".

### Is it possible to use glob without `import glob`?

**Yes, and it is actually preferred!** The old way required importing a separate module: `import glob`.
The modern way uses the `.glob()` method built right into `pathlib.Path`.

### Which is better?

Using **`Path.glob()`** is much better. Here is a quick comparison:

| Feature | Old `glob.glob()` | Modern `Path.glob()` |
| --- | --- | --- |
| **Imports** | Requires `import glob` | Built-in to `pathlib` (No extra imports) |
| **Returns** | A list of plain strings | An iterator of `Path` objects |
| **Readability** | `glob.glob("folder/*.csv")` | `folder.glob("*.csv")` |

Because `Path.glob()` returns `Path` objects, you can immediately do powerful things to the results without extra code:

```python
for file_path in folder.glob("*.csv"):
    print(file_path.name)      # Just the filename (e.g., "btc.csv")
    print(file_path.stem)      # The filename without extension (e.g., "btc")
    print(file_path.suffix)    # Just the extension (e.g., ".csv")

```

*********************************************************************

You’ve got it! `folder.glob("btc*")` is exactly how you would find files starting with "btc".


Fortunately, there is an incredibly easy, built-in way to sort them using Python's `sorted()` function.

---

### The Easy Way: Using `sorted()`

Because `pathlib` path objects are smart, Python already knows how to compare them alphabetically. You just wrap your glob in `sorted()`:

#### 1. Ascending Order (A to Z / 1 to 10)

```python
# Just wrap the glob in sorted()
sorted_files = sorted(folder.glob("*.csv"))

```

#### 2. Descending Order (Z to A / 10 to 1)

```python
# Add the reverse=True argument
sorted_files = sorted(folder.glob("*.csv"), reverse=True)

```

---

### Why this works so beautifully

The `.glob()` method returns a **generator** (an unsorted, one-time stream of files).

When you pass that generator into `sorted()`, Python:

1. Pulls all the files out of the generator.
2. Compares their file paths as strings.
3. Returns a clean, sorted **list** of `Path` objects.

---

### Putting it into your concatenation script

Here is how clean your script looks when you want to concatenate your crypto trades in perfect alphabetical/chronological order:

```python
from pathlib import Path
import pandas as pd

# 1. Define the folder (using your robust absolute path style!)
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'

# 2. Get the files in perfect ascending alphabetical order
sorted_csv_files = sorted(folder.glob("*.csv"))

# 3. Read and combine them 
combined_df = pd.concat([pd.read_csv(f) for f in sorted_csv_files], ignore_index=True)

# 4. Save the result
combined_df.to_csv(folder / "combined_output.csv", index=False)

```

> **Pro Tip on Filenames:** If your files are named by date, name them using the **YYYY-MM-DD** format (e.g., `btc_2026-06-01.csv`, `btc_2026-06-02.csv`). Alphabetical sorting on YYYY-MM-DD strings naturally doubles as perfect chronological sorting!

****************************************************

`'FURTHER info'`

Yes, **absolutely!** That is exactly what happens, and it is the main reason why using `pandas` is so much better than trying to merge files using basic text editors or manual scripting.

Here is a quick look at the "magic" happening under the hood to give you peace of mind:

### 1. `pd.read_csv()` strips the headers first

When Python runs `pd.read_csv()`, it immediately separates the first row (the header) from the rest of the data.

* It turns the header into the **column names** of a DataFrame object.
* It turns the actual rows of data into the **body** of the DataFrame.
* At this point, the header row is no longer treated as "data" or "text"—it is metadata.

### 2. `pd.concat()` aligns them seamlessly

When you concatenate them, `pandas` looks at the column names of each DataFrame:

* If the column names match perfectly (e.g., `Date`, `Ticker`, `Price`), `pandas` stacks the data rows directly on top of each other.
* The redundant header rows from files 2, 3, and 4 **do not** get repeated as rows in your final data. They are cleanly merged.

### 3. `to_csv(index=False)` writes a single, clean file

When you export the combined DataFrame back to a CSV:

* **One Header to Rule Them All:** `pandas` writes the column names *exactly once* at the very top of the new file.
* **No Messy Index Column:** By setting `index=False`, you tell Python *not* to write the DataFrame's row numbers (0, 1, 2, 3...) into the first column of your CSV.

### The Result

You get one continuous, perfectly uniform CSV file with a single header row at the very top, followed by all your data rows stacked seamlessly beneath it. No duplicates, no random middle-of-the-file headers, and no annoying auto-generated index columns!

---------------
It is absolutely **not an overload** for `pandas`! In fact, this is where `pandas` truly shines compared to almost any other tool.

It handles jumbled columns and different numbers of columns automatically, though there are a couple of small "gotchas" with different datatypes you should know about.

Here is exactly how `pandas` handles each of these three scenarios:

---

### 1. Jumbled Columns (Columns in a different order)

**How `pandas` handles it:** **Perfect Alignment.**
If `file1.csv` has columns in the order `[Date, Ticker, Price]` and `file2.csv` has them in the order `[Price, Date, Ticker]`, `pandas` does not care.

When you run `pd.concat()`, it matches columns **by their names, not by their position**. It will automatically rearrange the data from `file2.csv` so that the prices line up under `Price`, dates under `Date`, and tickers under `Ticker`.

---

### 2. Different Number of Columns (Missing columns)

**How `pandas` handles it:** **An "Outer Join" (Keeps everything, fills blanks with `NaN`).**
If `file1.csv` has columns `[Date, Ticker, Price]` and `file2.csv` has `[Date, Ticker, Price, Volume]`, `pandas` will:

1. Create a final table with **all 4 columns** (`Date`, `Ticker`, `Price`, `Volume`).
2. Populate the `Volume` column for the rows that came from `file2.csv`.
3. Fill the `Volume` column with **`NaN`** (Not a Number / empty/null) for all the rows that came from `file1.csv`.

---

### 3. Different Datatypes in the Same Column (The only "Gotcha")

**How `pandas` handles it:** **Upcasting (Type conversion).**
If `file1.csv` has a column called `ID` with integers (`101, 102`), and `file2.csv` has the `ID` column with floats (`103.0, 104.5`), `pandas` will "upcast" the entire column in the final combined file to floats (`101.0, 102.0, 103.0, 104.5`) so no data precision is lost.

* **The danger zone:** If `file1.csv` has integers (`101`) and `file2.csv` has text (`"None"` or `"N/A"`), `pandas` will convert the entire column to the `object` (string) datatype. It won't crash, but you might have to clean up that column later if you want to do math on it.

---

### Summary Table: How Pandas Handles the Chaos

| Scenario | What Pandas Does | Result in Final CSV |
| --- | --- | --- |
| **Columns out of order** | Automatically aligns by name | Perfectly aligned columns |
| **Missing columns in some files** | Creates the column anyway | Fills missing spots with empty cells (`NaN`) |
| **Mixed numbers and text** | Converts the column to text/object type | Saved as text (no data lost, but needs cleaning) |

Basically, `pandas` is built to be highly forgiving. It will do everything in its power to merge your files without crashing, leaving it up to you to decide how to handle any missing data (`NaN`) or mismatched datatypes afterward!