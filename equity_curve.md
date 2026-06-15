An equity curve is simply a plot of:

```text
X-axis = Trade number (or time)
Y-axis = Account equity
```

Example:

```text
Trade 0   = $10,000
Trade 1   = $10,120
Trade 2   = $10,050
Trade 3   = $10,240
Trade 4   = $10,500
...
```

After each closed trade, update the account balance and record it.

So your backtester could save:

```csv
trade_number,equity
0,10000
1,10120
2,10050
3,10240
4,10500
```

Then plot it.

---

### What a great equity curve looks like

Think:

```text
      /
     /
    /
   /
  /
 /
```

A steady climb.

Characteristics:

* Consistent upward slope
* Small pullbacks
* New equity highs reached regularly
* No prolonged stagnation

Example:

```text
12000 |          /
11500 |        /
11000 |      /
10500 |    /
10000 |  /
      +------------
```

This is what every trader wants.

---

### A dangerous equity curve

Looks like:

```text
12000 |      /\
11500 |     /  \
11000 |    /    \
10500 |   /      \
10000 |__/        \__
      +---------------
```

Characteristics:

* Large drawdowns
* Profits repeatedly given back
* Emotional nightmare in live trading

Even if final profit is positive, many traders abandon such systems.

---

### The "lucky strategy" curve

Looks like:

```text
10000 |___________/
      +-----------
```

Nothing happens for months.

Then one giant winner appears.

This is common in trend-following systems.

Not necessarily bad, but psychologically difficult.

---

### The curve professionals fear most

Looks like:

```text
12000 |\
11500 | \
11000 |  \
10500 |   \
10000 |    \
      +------
```

Downward slope.

No explanation needed.

---

### The hidden killer

Looks like:

```text
12000 |     /
11500 |    /
11000 |   /
10500 |  /
10000 | /
 9500 |/
      +-------
```

Seems fine.

But zoom in:

```text
12000 |      /\
11500 |     /  \
11000 |    /    \
10500 |   /      \
10000 |__/        \_
 8000 |
```

Huge drawdowns.

Many novice traders only look at final profit.

Professionals immediately ask:

> "How much pain was required to earn that profit?"

---

### The shape I would want for your future aggTrades bot

Something like:

```text
15000 |            /
14500 |          /
14000 |        /
13500 |      /
13000 |    /
12500 |  /
12000 |/
      +-------------
```

Notice:

* Upward slope
* Drawdowns exist
* Drawdowns are relatively shallow
* Recovery is quick
* New highs appear frequently

---

### Most important insight

When you begin testing strategies, don't ask:

> "Did it make money?"

Ask:

> "How did it make money?"

Two strategies can both make 50%.

Strategy A:

```text
Return: +50%
Max Drawdown: -12%
```

Strategy B:

```text
Return: +50%
Max Drawdown: -65%
```

Professionals choose Strategy A almost every time.

That's why, after Net Profit and Maximum Drawdown, the equity curve is often the first chart experienced system traders inspect. It reveals weaknesses that win rate, profit factor, and total return can easily hide.
