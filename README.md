# cow.fun

**Pointless things, expertly overengineered.**

[cow.fun](https://fun.theorangecow.org/) is a small, slowly growing collection of random games, experiments, and things that probably did not need to exist.

Built by [TheOrangeCow](https://github.com/TheOrangeCow) with too much free time.

## What is cow.fun?

cow.fun is a collection of weird little web games and experiments.

There is no grand purpose. Some games are competitive. Some are stupid. Some are surprisingly complicated for what they actually do.

The goal is simple:

> Make small ideas unnecessarily elaborate.

The site currently contains a growing collection of games and experiments, with new ones added over time.

## Features

* A collection of small browser games
* Random experiments and interactive projects
* Search for games
* Popularity tracking
* Individual game pages
* A growing collection of increasingly questionable ideas
* Simple, fast web interface

## Tech

cow.fun is built primarily with:

* Python
* Flask
* HTML
* CSS
* JavaScript
* SQLite

The project is structured around Flask routes, templates, static assets, and individual game implementations.

## Project Structure

```text
cow.fun/
├── routes/
├── static/
├── templates/
├── .github/
│   └── workflows/
├── main.py
├── requirements.txt
├── LICENSE
└── README.md
```

## Running locally

Clone the repository:

```bash
git clone https://github.com/TheOrangeCow/cow.fun.git
cd cow.fun
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

Or on Linux/macOS:

```bash
source venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the development server:

```bash
python main.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Adding a game

Games live alongside the rest of the cow.fun application and are connected through the Flask routing system.

A typical game should:

1. Have its own route
2. Have its own page or interface
3. Keep its assets organised
4. Work on desktop and mobile
5. Actually be playable
6. Ideally be at least slightly unnecessary

If a five-minute idea somehow turns into several hundred lines of code, you're probably doing it right.

## Contributing

Pull requests and ideas are welcome.

If you have a pointless game that deserves to exist, feel free to open an issue or submit a pull request.

Before contributing, keep the general spirit of the project in mind:

**Small idea. Weird execution. Unnecessarily polished.**

## License

cow.fun is licensed under the **GNU General Public License v3.0**.

See [`LICENSE`](LICENSE) for the full license text.

## Links

* **Website:** https://fun.theorangecow.org/
* **GitHub:** https://github.com/TheOrangeCow/cow.fun
* **TheOrangeCow:** https://theorangecow.org/

---

Made by **TheOrangeCow**.

*There was probably a better use of time.*
