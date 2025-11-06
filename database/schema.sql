CREATE TABLE users (
id INTEGER PRIMARY KEY NOT NULL,
cash NUMERIC NOT NULL DEFAULT 10000.00, created DATE NOT NULL DEFAULT (date()), username TEXT null on conflict ignore);

CREATE TABLE history (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER NOT NULL,
stock TEXT NOT NULL,
price NUMERIC NOT NULL,
quantity INTEGER NOT NULL,
time NUMERIC DEFAULT (datetime('now')),
FOREIGN KEY (user_id) REFERENCES users(id));

CREATE TABLE user_savings (
user_id INTEGER NOT NULL,
stock TEXT NOT NULL,
quantity INTEGER NOT NULL,
PRIMARY KEY (user_id, stock),
FOREIGN KEY (user_id) REFERENCES users(id));
CREATE TRIGGER delete_zero_quantity
AFTER UPDATE ON user_savings
FOR EACH ROW
WHEN NEW.quantity = 0
BEGIN
    DELETE FROM user_savings WHERE user_id = NEW.user_id AND stock = NEW.stock;
END;