from database import Base, engine
from models import NegotiatorHistory, NegotiatorState

def create_all_tables():
    print("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")

if __name__ == "__main__":
    create_all_tables()