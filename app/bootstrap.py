from ui.gui_dashboard import DashboardBurgos
from infrastructure import db


def main():
    db.inicializar()
    app = DashboardBurgos()
    app.mainloop()


if __name__ == "__main__":
    main()
