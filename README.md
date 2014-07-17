# been

Been is a minimalistic life stream archiver and aggregator. It fetches *events* from a set of *sources*, such as GitHub commits, reddit comments, and tweets, logging them in a *store* (couchdb or redis).

Been was designed with a companion web interface, [wake](https://github.com/chromakode/wake), to form a simple website engine. In addition to online feeds, been can read markdown files out of a local directory or git repository, serving as the data backend of a blog website.

Been is small, general purpose, and hackable. Left its own devices, been provides a persistent and centralized store of often transient web activity. This can be useful for personal queries and statistical analysis.

The name "been" is a shortening of "where I've been" / "what I've been up to".

### origin story

As I prepared to join reddit in 2010, Jeremy Edberg advised me to update my website, since I wouldn't likely find time to do so afterward. *Been* and *wake* were my attempt to make a website that would update itself in my coming absence.

Been was also inspired by David Cramer's excellent [Lifestream WordPress plugin](http://www.enthropia.com/labs/wp-lifestream/).
