Your plan is to utilize the **idle gap** between sensor transmissions to perform database maintenance. Since your hardware transmits once per minute, you have a predictable 59-second window where the CPU and Database are doing nothing.

Here is the conceptual breakdown and the execution steps:

### The Core Concept

Instead of running a second "brain" (thread or process) to manage history, you turn your Bridge into a **Sequential Manager**. It follows a simple loop:

1. **Listen** for data.
2. **Commit** data to the Raw table.
3. **Check** if the hour has rolled over.
4. **Summarize** if needed.
5. **Idle** until the next packet.

---

### Execution Steps for Tomorrow

#### 1. The "Hour Tracker"

You need a state variable (e.g., `last_processed_hour`) initialized when the script starts. Every time a packet is saved, you compare the current hour to this variable. If they don't match, the "Maintenance Window" opens.

#### 2. The Aggregation Logic (The "Crunch")

Inside the maintenance window, you execute three SQL commands in order:

* **Hourly Summary:** Query the `mesures` table for all rows where the timestamp matches the *previous* hour. Calculate the Min, Max, and Average for every sensor and `INSERT` that single result into your `hourly_history` table.
* **Daily Summary:** Query the `hourly_history` table for the *previous* day. Aggregate those 24 rows into a single row for `daily_history`.
* **The Prune:** Delete rows from the `mesures` table that are older than your desired threshold (e.g., 24 or 48 hours). This keeps the "Raw" table from ever growing past ~2,800 rows.

#### 3. Database Optimization

Since you are deleting thousands of rows over time, the SQLite file will develop "empty space" (fragmentation). Once a day—ideally during the 3:00 AM maintenance window—run a `VACUUM` command to shrink the file size and keep it fast.

#### 4. Handling Constraints

* **Timeouts:** Ensure your database connection has a `timeout` parameter. Even though you are sequential, it’s good practice if you ever decide to open the database with a GUI tool while the script is running.
* **WAL Mode:** Ensure your script enables **Write-Ahead Logging** on startup. This makes the transition between writing raw data and reading/deleting history much smoother.

---

### The Result

By the time the next packet arrives 60 seconds later, your script has already finished the math, cleaned up the old data, and is sitting quietly waiting for the next serial string. You’ve turned a potential 5-million-row headache into a self-cleaning, tiered system.

**Would you like me to explain how to handle the "Previous Hour" logic so you don't accidentally aggregate the current (incomplete) hour?**