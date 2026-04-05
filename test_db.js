const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const dbPath = path.join(__dirname, 'data', 'audit.db');
const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, (err) => {
  if (err) {
    console.error(err.message);
  }
  console.log('Connected to the audit.db database.');
});

db.serialize(() => {
  db.each(`SELECT period, type, category, gl_code, month_actual, month_budget, ytd_actual, ytd_budget, annual_budget FROM income_statement_ytd LIMIT 1`, (err, row) => {
    if (err) {
      console.error('Error on income_statement_ytd:', err.message);
    }
    console.log(row);
  });
});

db.close();
