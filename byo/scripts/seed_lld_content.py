#!/usr/bin/env python3
"""
Seed Low-Level Design (LLD) problems and teaching plans into MongoDB.

LLD fills the gap between DSA (algorithmic coding) and HLD (distributed systems).
LLD is about designing classes, interfaces, and components for a single-service app.

- LLD problems  -> capacity.sd_problems   (with type="lld")
- LLD plans     -> capacity.teaching_plans (with type="lld")

Usage:
    python -m byo.scripts.seed_lld_content
    python -m byo.scripts.seed_lld_content --uri "mongodb+srv://..."
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# 15 LLD Problems
# ---------------------------------------------------------------------------

LLD_PROBLEMS = [
    # -----------------------------------------------------------------------
    # 1. Parking Lot System
    # -----------------------------------------------------------------------
    {
        "num": 1,
        "name": "Parking Lot System",
        "slug": "parking-lot-system",
        "difficulty": "medium",
        "type": "lld",
        "description": (
            "Design an object-oriented parking lot that supports multiple floors, "
            "different vehicle types (motorcycle, car, truck), and automated ticketing "
            "with hourly pricing. The system should track available spots in real time "
            "and calculate fees on exit."
        ),
        "topics": ["oop", "design_patterns", "state_management"],
        "requirements": [
            "Support multiple floors, each with configurable spot counts per vehicle type",
            "Park a vehicle in the nearest available compatible spot and issue a ticket",
            "Unpark a vehicle given a ticket and calculate the fee based on duration",
            "Track real-time availability per floor and per vehicle type",
            "Handle concurrent entry/exit at multiple gates",
            "Support different pricing strategies (hourly flat, tiered, weekend surcharge)",
        ],
        "entities": [
            "ParkingLot", "ParkingFloor", "ParkingSpot", "Vehicle",
            "Car", "Motorcycle", "Truck", "Ticket", "PricingStrategy",
            "EntranceGate", "ExitGate", "DisplayBoard",
        ],
        "design_patterns": ["Strategy", "Singleton", "Factory", "Observer"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "from datetime import datetime\n"
                "\n"
                "\n"
                "class VehicleType(Enum):\n"
                "    MOTORCYCLE = 1\n"
                "    CAR = 2\n"
                "    TRUCK = 3\n"
                "\n"
                "\n"
                "class Vehicle:\n"
                "    def __init__(self, license_plate: str, vehicle_type: VehicleType):\n"
                "        self.license_plate = license_plate\n"
                "        self.vehicle_type = vehicle_type\n"
                "\n"
                "\n"
                "class ParkingSpot:\n"
                "    def __init__(self, spot_id: str, spot_type: VehicleType, floor: int):\n"
                "        self.spot_id = spot_id\n"
                "        self.spot_type = spot_type\n"
                "        self.floor = floor\n"
                "        self.vehicle = None\n"
                "\n"
                "    def is_available(self) -> bool:\n"
                "        pass\n"
                "\n"
                "    def assign_vehicle(self, vehicle: Vehicle) -> None:\n"
                "        pass\n"
                "\n"
                "    def remove_vehicle(self) -> Vehicle:\n"
                "        pass\n"
                "\n"
                "\n"
                "class PricingStrategy(ABC):\n"
                "    @abstractmethod\n"
                "    def calculate_fee(self, entry_time: datetime, exit_time: datetime, vehicle_type: VehicleType) -> float:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Ticket:\n"
                "    def __init__(self, ticket_id: str, vehicle: Vehicle, spot: ParkingSpot):\n"
                "        self.ticket_id = ticket_id\n"
                "        self.vehicle = vehicle\n"
                "        self.spot = spot\n"
                "        self.entry_time = datetime.now()\n"
                "\n"
                "\n"
                "class ParkingLot:\n"
                "    def __init__(self, name: str, num_floors: int, pricing: PricingStrategy):\n"
                "        pass\n"
                "\n"
                "    def park(self, vehicle: Vehicle) -> Ticket:\n"
                "        pass\n"
                "\n"
                "    def unpark(self, ticket: Ticket) -> float:\n"
                "        pass\n"
                "\n"
                "    def get_availability(self) -> dict:\n"
                "        pass\n"
            ),
            "java": (
                "public enum VehicleType { MOTORCYCLE, CAR, TRUCK }\n"
                "\n"
                "public abstract class Vehicle {\n"
                "    private String licensePlate;\n"
                "    private VehicleType type;\n"
                "    public Vehicle(String licensePlate, VehicleType type) {\n"
                "        this.licensePlate = licensePlate;\n"
                "        this.type = type;\n"
                "    }\n"
                "    public VehicleType getType() { return type; }\n"
                "    public String getLicensePlate() { return licensePlate; }\n"
                "}\n"
                "\n"
                "public class ParkingSpot {\n"
                "    private String spotId;\n"
                "    private VehicleType spotType;\n"
                "    private int floor;\n"
                "    private Vehicle vehicle;\n"
                "    public boolean isAvailable() { return vehicle == null; }\n"
                "    public void assignVehicle(Vehicle v) { /* TODO */ }\n"
                "    public Vehicle removeVehicle() { /* TODO */ return null; }\n"
                "}\n"
                "\n"
                "public interface PricingStrategy {\n"
                "    double calculateFee(LocalDateTime entry, LocalDateTime exit, VehicleType type);\n"
                "}\n"
                "\n"
                "public class Ticket {\n"
                "    private String ticketId;\n"
                "    private Vehicle vehicle;\n"
                "    private ParkingSpot spot;\n"
                "    private LocalDateTime entryTime;\n"
                "}\n"
                "\n"
                "public class ParkingLot {\n"
                "    public ParkingLot(String name, int numFloors, PricingStrategy pricing) {}\n"
                "    public Ticket park(Vehicle vehicle) { return null; }\n"
                "    public double unpark(Ticket ticket) { return 0; }\n"
                "    public Map<VehicleType, Integer> getAvailability() { return null; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 2. Library Management System
    # -----------------------------------------------------------------------
    {
        "num": 2,
        "name": "Library Management System",
        "slug": "library-management-system",
        "difficulty": "easy",
        "type": "lld",
        "description": (
            "Design a library management system that tracks books, members, "
            "borrowing/returning, reservations, and fine calculation. The system "
            "should handle multiple copies of the same book and enforce borrowing limits."
        ),
        "topics": ["oop", "design_patterns", "state_management"],
        "requirements": [
            "Add, remove, and search books by title, author, or ISBN",
            "Register members and track their borrowing history",
            "Issue a book copy to a member (max 5 active borrows per member)",
            "Return a book and calculate overdue fines ($1/day)",
            "Reserve a book if all copies are checked out; notify when available",
            "Support multiple copies of the same book (BookItem vs Book)",
        ],
        "entities": [
            "Library", "Book", "BookItem", "Member", "Librarian",
            "BookLending", "BookReservation", "Fine", "Catalog",
            "Author", "Rack",
        ],
        "design_patterns": ["Observer", "Repository", "Factory"],
        "starter_code": {
            "python": (
                "from enum import Enum\n"
                "from datetime import datetime, timedelta\n"
                "\n"
                "\n"
                "class BookStatus(Enum):\n"
                "    AVAILABLE = 1\n"
                "    CHECKED_OUT = 2\n"
                "    RESERVED = 3\n"
                "    LOST = 4\n"
                "\n"
                "\n"
                "class Book:\n"
                "    def __init__(self, isbn: str, title: str, author: str, publisher: str):\n"
                "        self.isbn = isbn\n"
                "        self.title = title\n"
                "        self.author = author\n"
                "        self.publisher = publisher\n"
                "\n"
                "\n"
                "class BookItem:\n"
                "    \"\"\"A physical copy of a Book.\"\"\"\n"
                "    def __init__(self, barcode: str, book: Book):\n"
                "        self.barcode = barcode\n"
                "        self.book = book\n"
                "        self.status = BookStatus.AVAILABLE\n"
                "        self.due_date = None\n"
                "        self.borrowed_by = None\n"
                "\n"
                "    def checkout(self, member: 'Member') -> bool:\n"
                "        pass\n"
                "\n"
                "    def return_book(self) -> float:\n"
                "        \"\"\"Return book and return overdue fine amount.\"\"\"\n"
                "        pass\n"
                "\n"
                "\n"
                "class Member:\n"
                "    MAX_BOOKS = 5\n"
                "\n"
                "    def __init__(self, member_id: str, name: str):\n"
                "        self.member_id = member_id\n"
                "        self.name = name\n"
                "        self.active_borrows: list[BookItem] = []\n"
                "        self.total_fine = 0.0\n"
                "\n"
                "    def can_borrow(self) -> bool:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Library:\n"
                "    def __init__(self):\n"
                "        pass\n"
                "\n"
                "    def add_book(self, book: Book, copies: int) -> list[BookItem]:\n"
                "        pass\n"
                "\n"
                "    def search(self, query: str) -> list[Book]:\n"
                "        pass\n"
                "\n"
                "    def checkout(self, member: Member, barcode: str) -> bool:\n"
                "        pass\n"
                "\n"
                "    def return_book(self, member: Member, barcode: str) -> float:\n"
                "        pass\n"
                "\n"
                "    def reserve(self, member: Member, isbn: str) -> bool:\n"
                "        pass\n"
            ),
            "java": (
                "public enum BookStatus { AVAILABLE, CHECKED_OUT, RESERVED, LOST }\n"
                "\n"
                "public class Book {\n"
                "    private String isbn, title, author, publisher;\n"
                "    public Book(String isbn, String title, String author, String publisher) {}\n"
                "}\n"
                "\n"
                "public class BookItem {\n"
                "    private String barcode;\n"
                "    private Book book;\n"
                "    private BookStatus status;\n"
                "    private LocalDate dueDate;\n"
                "    private Member borrowedBy;\n"
                "    public boolean checkout(Member member) { return false; }\n"
                "    public double returnBook() { return 0; }\n"
                "}\n"
                "\n"
                "public class Member {\n"
                "    private static final int MAX_BOOKS = 5;\n"
                "    private String memberId, name;\n"
                "    private List<BookItem> activeBorrows;\n"
                "    public boolean canBorrow() { return activeBorrows.size() < MAX_BOOKS; }\n"
                "}\n"
                "\n"
                "public class Library {\n"
                "    public List<BookItem> addBook(Book book, int copies) { return null; }\n"
                "    public List<Book> search(String query) { return null; }\n"
                "    public boolean checkout(Member member, String barcode) { return false; }\n"
                "    public double returnBook(Member member, String barcode) { return 0; }\n"
                "    public boolean reserve(Member member, String isbn) { return false; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 3. Elevator System
    # -----------------------------------------------------------------------
    {
        "num": 3,
        "name": "Elevator System",
        "slug": "elevator-system",
        "difficulty": "hard",
        "type": "lld",
        "description": (
            "Design an elevator control system for a building with multiple elevators. "
            "The system must efficiently schedule elevator dispatch using algorithms like "
            "SCAN (elevator algorithm) or LOOK, handle concurrent requests from multiple "
            "floors, and minimize average wait time."
        ),
        "topics": ["oop", "design_patterns", "concurrency", "scheduling"],
        "requirements": [
            "Support N elevators serving M floors",
            "Handle external requests (floor button: up/down) and internal requests (cabin button: destination floor)",
            "Implement an elevator scheduling algorithm (SCAN, LOOK, or shortest-seek-first)",
            "Each elevator has states: IDLE, MOVING_UP, MOVING_DOWN, DOOR_OPEN",
            "Dispatch the optimal elevator for a new request (minimize wait time)",
            "Handle edge cases: overweight, door obstruction, emergency stop, maintenance mode",
        ],
        "entities": [
            "ElevatorSystem", "Elevator", "ElevatorController", "Dispatcher",
            "Request", "ExternalRequest", "InternalRequest",
            "Floor", "Door", "Display", "Button",
        ],
        "design_patterns": ["Strategy", "State", "Observer", "Singleton", "Command"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "from collections import deque\n"
                "\n"
                "\n"
                "class Direction(Enum):\n"
                "    UP = 1\n"
                "    DOWN = 2\n"
                "    IDLE = 3\n"
                "\n"
                "\n"
                "class ElevatorState(Enum):\n"
                "    IDLE = 1\n"
                "    MOVING_UP = 2\n"
                "    MOVING_DOWN = 3\n"
                "    DOOR_OPEN = 4\n"
                "    MAINTENANCE = 5\n"
                "\n"
                "\n"
                "class Request:\n"
                "    def __init__(self, floor: int, direction: Direction = None):\n"
                "        self.floor = floor\n"
                "        self.direction = direction\n"
                "\n"
                "\n"
                "class Elevator:\n"
                "    def __init__(self, elevator_id: int, capacity: int, min_floor: int, max_floor: int):\n"
                "        self.elevator_id = elevator_id\n"
                "        self.capacity = capacity\n"
                "        self.current_floor = min_floor\n"
                "        self.state = ElevatorState.IDLE\n"
                "        self.destinations: list[int] = []\n"
                "\n"
                "    def add_destination(self, floor: int) -> None:\n"
                "        pass\n"
                "\n"
                "    def move(self) -> None:\n"
                "        \"\"\"Move one step toward next destination.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def open_door(self) -> None:\n"
                "        pass\n"
                "\n"
                "    def close_door(self) -> None:\n"
                "        pass\n"
                "\n"
                "\n"
                "class DispatchStrategy(ABC):\n"
                "    @abstractmethod\n"
                "    def select_elevator(self, request: Request, elevators: list[Elevator]) -> Elevator:\n"
                "        pass\n"
                "\n"
                "\n"
                "class ElevatorSystem:\n"
                "    def __init__(self, num_elevators: int, num_floors: int, strategy: DispatchStrategy):\n"
                "        pass\n"
                "\n"
                "    def request_elevator(self, floor: int, direction: Direction) -> None:\n"
                "        \"\"\"External hall button press.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def select_floor(self, elevator_id: int, floor: int) -> None:\n"
                "        \"\"\"Internal cabin button press.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def step(self) -> None:\n"
                "        \"\"\"Advance simulation by one time unit.\"\"\"\n"
                "        pass\n"
            ),
            "java": (
                "public enum Direction { UP, DOWN, IDLE }\n"
                "public enum ElevatorState { IDLE, MOVING_UP, MOVING_DOWN, DOOR_OPEN, MAINTENANCE }\n"
                "\n"
                "public class Request {\n"
                "    private int floor;\n"
                "    private Direction direction;\n"
                "    public Request(int floor, Direction direction) {\n"
                "        this.floor = floor; this.direction = direction;\n"
                "    }\n"
                "}\n"
                "\n"
                "public class Elevator {\n"
                "    private int id, capacity, currentFloor;\n"
                "    private ElevatorState state;\n"
                "    private TreeSet<Integer> destinations;\n"
                "    public void addDestination(int floor) {}\n"
                "    public void move() {}\n"
                "    public void openDoor() {}\n"
                "    public void closeDoor() {}\n"
                "}\n"
                "\n"
                "public interface DispatchStrategy {\n"
                "    Elevator selectElevator(Request request, List<Elevator> elevators);\n"
                "}\n"
                "\n"
                "public class ElevatorSystem {\n"
                "    private List<Elevator> elevators;\n"
                "    private DispatchStrategy strategy;\n"
                "    public void requestElevator(int floor, Direction dir) {}\n"
                "    public void selectFloor(int elevatorId, int floor) {}\n"
                "    public void step() {}\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 4. Vending Machine
    # -----------------------------------------------------------------------
    {
        "num": 4,
        "name": "Vending Machine",
        "slug": "vending-machine",
        "difficulty": "easy",
        "type": "lld",
        "description": (
            "Design a vending machine that manages product inventory, accepts multiple "
            "payment methods, dispenses products, and returns change. The machine transitions "
            "through well-defined states (idle, accepting money, dispensing, returning change) "
            "modeled with the State pattern."
        ),
        "topics": ["oop", "design_patterns", "state_machine"],
        "requirements": [
            "Display available products with prices and remaining quantity",
            "Accept coins (1c, 5c, 10c, 25c) and bills ($1, $5)",
            "Allow product selection after sufficient money is inserted",
            "Dispense the product and return correct change",
            "Handle insufficient funds, out-of-stock, and exact-change-only modes",
            "Admin: restock products, collect revenue, reset machine",
        ],
        "entities": [
            "VendingMachine", "State", "IdleState", "HasMoneyState",
            "DispensingState", "Product", "Inventory", "Coin", "Bill",
        ],
        "design_patterns": ["State", "Singleton", "Factory"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "\n"
                "\n"
                "class Coin(Enum):\n"
                "    PENNY = 1\n"
                "    NICKEL = 5\n"
                "    DIME = 10\n"
                "    QUARTER = 25\n"
                "\n"
                "\n"
                "class Product:\n"
                "    def __init__(self, name: str, price: int, quantity: int):\n"
                "        self.name = name\n"
                "        self.price = price  # in cents\n"
                "        self.quantity = quantity\n"
                "\n"
                "\n"
                "class VendingMachineState(ABC):\n"
                "    @abstractmethod\n"
                "    def insert_coin(self, coin: Coin) -> None:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def select_product(self, product_code: str) -> None:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def dispense(self) -> None:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def cancel(self) -> list[Coin]:\n"
                "        pass\n"
                "\n"
                "\n"
                "class VendingMachine:\n"
                "    def __init__(self):\n"
                "        self.inventory: dict[str, Product] = {}\n"
                "        self.current_balance = 0\n"
                "        self.state: VendingMachineState = None  # set to IdleState\n"
                "\n"
                "    def insert_coin(self, coin: Coin) -> None:\n"
                "        pass\n"
                "\n"
                "    def select_product(self, product_code: str) -> None:\n"
                "        pass\n"
                "\n"
                "    def dispense(self) -> Product:\n"
                "        pass\n"
                "\n"
                "    def cancel(self) -> list[Coin]:\n"
                "        pass\n"
                "\n"
                "    def restock(self, product_code: str, quantity: int) -> None:\n"
                "        pass\n"
            ),
            "java": (
                "public enum Coin { PENNY(1), NICKEL(5), DIME(10), QUARTER(25);\n"
                "    private final int value;\n"
                "    Coin(int value) { this.value = value; }\n"
                "    public int getValue() { return value; }\n"
                "}\n"
                "\n"
                "public class Product {\n"
                "    private String name;\n"
                "    private int price; // cents\n"
                "    private int quantity;\n"
                "}\n"
                "\n"
                "public interface VendingMachineState {\n"
                "    void insertCoin(Coin coin);\n"
                "    void selectProduct(String code);\n"
                "    void dispense();\n"
                "    List<Coin> cancel();\n"
                "}\n"
                "\n"
                "public class VendingMachine {\n"
                "    private Map<String, Product> inventory;\n"
                "    private int currentBalance;\n"
                "    private VendingMachineState state;\n"
                "    public void insertCoin(Coin coin) {}\n"
                "    public void selectProduct(String code) {}\n"
                "    public Product dispense() { return null; }\n"
                "    public List<Coin> cancel() { return null; }\n"
                "    public void restock(String code, int qty) {}\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 5. ATM System
    # -----------------------------------------------------------------------
    {
        "num": 5,
        "name": "ATM System",
        "slug": "atm-system",
        "difficulty": "medium",
        "type": "lld",
        "description": (
            "Design an ATM system that authenticates users via card + PIN, supports "
            "balance inquiry, cash withdrawal, deposit, and transfer operations. "
            "The system uses a chain of handlers for transaction processing and "
            "the State pattern for the ATM's operating modes."
        ),
        "topics": ["oop", "design_patterns", "state_machine", "chain_of_responsibility"],
        "requirements": [
            "Authenticate user with card number and PIN (max 3 attempts, then lock card)",
            "Support operations: balance inquiry, withdraw, deposit, transfer between accounts",
            "Withdrawal must check: sufficient account balance, sufficient cash in ATM, dispense correct denominations",
            "Dispense cash using fewest bills (greedy: $100, $50, $20, $10, $5, $1)",
            "Maintain transaction history with timestamps",
            "Handle concurrent access (one user at a time per ATM, but multiple ATMs on same bank)",
        ],
        "entities": [
            "ATM", "ATMState", "Card", "Account", "Bank",
            "Transaction", "CashDispenser", "CardReader", "Screen",
            "Keypad", "WithdrawTransaction", "DepositTransaction",
        ],
        "design_patterns": ["State", "Chain of Responsibility", "Command", "Singleton"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "from datetime import datetime\n"
                "\n"
                "\n"
                "class TransactionType(Enum):\n"
                "    BALANCE_INQUIRY = 1\n"
                "    WITHDRAW = 2\n"
                "    DEPOSIT = 3\n"
                "    TRANSFER = 4\n"
                "\n"
                "\n"
                "class Account:\n"
                "    def __init__(self, account_number: str, pin: str, balance: float):\n"
                "        self.account_number = account_number\n"
                "        self.pin = pin\n"
                "        self.balance = balance\n"
                "\n"
                "    def withdraw(self, amount: float) -> bool:\n"
                "        pass\n"
                "\n"
                "    def deposit(self, amount: float) -> None:\n"
                "        pass\n"
                "\n"
                "    def get_balance(self) -> float:\n"
                "        pass\n"
                "\n"
                "\n"
                "class CashDispenser:\n"
                "    DENOMINATIONS = [100, 50, 20, 10, 5, 1]\n"
                "\n"
                "    def __init__(self, initial_cash: dict[int, int]):\n"
                "        self.cash = initial_cash  # denomination -> count\n"
                "\n"
                "    def can_dispense(self, amount: int) -> bool:\n"
                "        pass\n"
                "\n"
                "    def dispense(self, amount: int) -> dict[int, int]:\n"
                "        \"\"\"Return {denomination: count} or raise error.\"\"\"\n"
                "        pass\n"
                "\n"
                "\n"
                "class ATMState(ABC):\n"
                "    @abstractmethod\n"
                "    def insert_card(self, card_number: str) -> None:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def enter_pin(self, pin: str) -> bool:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def select_transaction(self, txn_type: TransactionType) -> None:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def execute_transaction(self, **kwargs) -> dict:\n"
                "        pass\n"
                "\n"
                "\n"
                "class ATM:\n"
                "    def __init__(self, atm_id: str, bank: 'Bank', dispenser: CashDispenser):\n"
                "        self.atm_id = atm_id\n"
                "        self.bank = bank\n"
                "        self.dispenser = dispenser\n"
                "        self.state: ATMState = None\n"
                "        self.current_account: Account = None\n"
                "\n"
                "    def insert_card(self, card_number: str) -> None:\n"
                "        pass\n"
                "\n"
                "    def enter_pin(self, pin: str) -> bool:\n"
                "        pass\n"
                "\n"
                "    def withdraw(self, amount: int) -> dict[int, int]:\n"
                "        pass\n"
                "\n"
                "    def deposit(self, amount: float) -> None:\n"
                "        pass\n"
                "\n"
                "    def check_balance(self) -> float:\n"
                "        pass\n"
            ),
            "java": (
                "public enum TransactionType { BALANCE_INQUIRY, WITHDRAW, DEPOSIT, TRANSFER }\n"
                "\n"
                "public class Account {\n"
                "    private String accountNumber;\n"
                "    private String pin;\n"
                "    private double balance;\n"
                "    public boolean withdraw(double amount) { return false; }\n"
                "    public void deposit(double amount) {}\n"
                "    public double getBalance() { return balance; }\n"
                "}\n"
                "\n"
                "public class CashDispenser {\n"
                "    private Map<Integer, Integer> cash; // denomination -> count\n"
                "    public boolean canDispense(int amount) { return false; }\n"
                "    public Map<Integer, Integer> dispense(int amount) { return null; }\n"
                "}\n"
                "\n"
                "public interface ATMState {\n"
                "    void insertCard(String cardNumber);\n"
                "    boolean enterPin(String pin);\n"
                "    void selectTransaction(TransactionType type);\n"
                "}\n"
                "\n"
                "public class ATM {\n"
                "    private String atmId;\n"
                "    private Bank bank;\n"
                "    private CashDispenser dispenser;\n"
                "    private ATMState state;\n"
                "    public void insertCard(String cardNumber) {}\n"
                "    public boolean enterPin(String pin) { return false; }\n"
                "    public Map<Integer, Integer> withdraw(int amount) { return null; }\n"
                "    public void deposit(double amount) {}\n"
                "    public double checkBalance() { return 0; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 6. Hotel Booking System
    # -----------------------------------------------------------------------
    {
        "num": 6,
        "name": "Hotel Booking System",
        "slug": "hotel-booking-system",
        "difficulty": "medium",
        "type": "lld",
        "description": (
            "Design a hotel booking system that manages rooms of different types, "
            "handles reservations with date ranges, supports check-in/check-out, "
            "and calculates bills with room charges plus add-on services. "
            "The system must prevent double-booking and handle cancellations."
        ),
        "topics": ["oop", "design_patterns", "booking_systems", "date_handling"],
        "requirements": [
            "Manage rooms of different types (Standard, Deluxe, Suite) with per-night pricing",
            "Search available rooms for a given date range and room type",
            "Create, confirm, and cancel reservations (cancellation policy: free if >24h before check-in)",
            "Check-in and check-out guests; generate itemized bill",
            "Support add-on services (room service, laundry, minibar) charged to the room",
            "Prevent double-booking: a room cannot have overlapping confirmed reservations",
        ],
        "entities": [
            "Hotel", "Room", "RoomType", "Guest", "Reservation",
            "ReservationStatus", "Bill", "Service", "Payment",
            "RoomKey", "Receptionist",
        ],
        "design_patterns": ["Factory", "Strategy", "Observer", "Builder"],
        "starter_code": {
            "python": (
                "from enum import Enum\n"
                "from datetime import date\n"
                "\n"
                "\n"
                "class RoomType(Enum):\n"
                "    STANDARD = 1\n"
                "    DELUXE = 2\n"
                "    SUITE = 3\n"
                "\n"
                "\n"
                "class ReservationStatus(Enum):\n"
                "    PENDING = 1\n"
                "    CONFIRMED = 2\n"
                "    CHECKED_IN = 3\n"
                "    CHECKED_OUT = 4\n"
                "    CANCELLED = 5\n"
                "\n"
                "\n"
                "class Room:\n"
                "    def __init__(self, room_number: str, room_type: RoomType, price_per_night: float):\n"
                "        self.room_number = room_number\n"
                "        self.room_type = room_type\n"
                "        self.price_per_night = price_per_night\n"
                "\n"
                "    def is_available(self, check_in: date, check_out: date) -> bool:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Reservation:\n"
                "    def __init__(self, guest: 'Guest', room: Room, check_in: date, check_out: date):\n"
                "        self.guest = guest\n"
                "        self.room = room\n"
                "        self.check_in = check_in\n"
                "        self.check_out = check_out\n"
                "        self.status = ReservationStatus.PENDING\n"
                "        self.services: list[tuple[str, float]] = []\n"
                "\n"
                "    def confirm(self) -> None:\n"
                "        pass\n"
                "\n"
                "    def cancel(self) -> float:\n"
                "        \"\"\"Return cancellation fee.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def add_service(self, name: str, cost: float) -> None:\n"
                "        pass\n"
                "\n"
                "    def generate_bill(self) -> dict:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Hotel:\n"
                "    def __init__(self, name: str):\n"
                "        self.name = name\n"
                "        self.rooms: list[Room] = []\n"
                "        self.reservations: list[Reservation] = []\n"
                "\n"
                "    def search_available_rooms(self, room_type: RoomType, check_in: date, check_out: date) -> list[Room]:\n"
                "        pass\n"
                "\n"
                "    def make_reservation(self, guest: 'Guest', room: Room, check_in: date, check_out: date) -> Reservation:\n"
                "        pass\n"
                "\n"
                "    def check_in(self, reservation: Reservation) -> None:\n"
                "        pass\n"
                "\n"
                "    def check_out(self, reservation: Reservation) -> dict:\n"
                "        pass\n"
            ),
            "java": (
                "public enum RoomType { STANDARD, DELUXE, SUITE }\n"
                "public enum ReservationStatus { PENDING, CONFIRMED, CHECKED_IN, CHECKED_OUT, CANCELLED }\n"
                "\n"
                "public class Room {\n"
                "    private String roomNumber;\n"
                "    private RoomType type;\n"
                "    private double pricePerNight;\n"
                "    public boolean isAvailable(LocalDate checkIn, LocalDate checkOut) { return false; }\n"
                "}\n"
                "\n"
                "public class Reservation {\n"
                "    private Guest guest;\n"
                "    private Room room;\n"
                "    private LocalDate checkIn, checkOut;\n"
                "    private ReservationStatus status;\n"
                "    public void confirm() {}\n"
                "    public double cancel() { return 0; }\n"
                "    public Map<String, Object> generateBill() { return null; }\n"
                "}\n"
                "\n"
                "public class Hotel {\n"
                "    private String name;\n"
                "    private List<Room> rooms;\n"
                "    private List<Reservation> reservations;\n"
                "    public List<Room> searchAvailable(RoomType type, LocalDate in, LocalDate out) { return null; }\n"
                "    public Reservation makeReservation(Guest guest, Room room, LocalDate in, LocalDate out) { return null; }\n"
                "    public void checkIn(Reservation r) {}\n"
                "    public Map<String, Object> checkOut(Reservation r) { return null; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 7. Movie Ticket Booking (BookMyShow)
    # -----------------------------------------------------------------------
    {
        "num": 7,
        "name": "Movie Ticket Booking System",
        "slug": "movie-ticket-booking-system",
        "difficulty": "hard",
        "type": "lld",
        "description": (
            "Design a movie ticket booking system like BookMyShow. The system manages "
            "theaters, screens, shows, and seat selection with concurrency control to "
            "prevent double-booking of seats. Supports seat maps, pricing tiers, "
            "and time-limited seat holds."
        ),
        "topics": ["oop", "design_patterns", "concurrency", "booking_systems"],
        "requirements": [
            "Manage cities, theaters, screens, and movie showtimes",
            "Display seat map for a show with real-time availability (available, held, booked)",
            "Allow users to select and temporarily hold seats (5-minute lock)",
            "Complete booking with payment; release held seats on timeout or cancellation",
            "Prevent two users from booking the same seat (optimistic locking / compare-and-swap)",
            "Support different seat tiers (Silver, Gold, Platinum) with different prices",
        ],
        "entities": [
            "Movie", "Theater", "Screen", "Show", "Seat",
            "SeatType", "Booking", "BookingStatus", "Payment",
            "User", "City", "SeatHold", "SeatMap",
        ],
        "design_patterns": ["Builder", "Observer", "Strategy", "Singleton"],
        "starter_code": {
            "python": (
                "from enum import Enum\n"
                "from datetime import datetime\n"
                "import threading\n"
                "\n"
                "\n"
                "class SeatType(Enum):\n"
                "    SILVER = 1\n"
                "    GOLD = 2\n"
                "    PLATINUM = 3\n"
                "\n"
                "\n"
                "class SeatStatus(Enum):\n"
                "    AVAILABLE = 1\n"
                "    HELD = 2\n"
                "    BOOKED = 3\n"
                "\n"
                "\n"
                "class Seat:\n"
                "    def __init__(self, seat_id: str, row: str, number: int, seat_type: SeatType):\n"
                "        self.seat_id = seat_id\n"
                "        self.row = row\n"
                "        self.number = number\n"
                "        self.seat_type = seat_type\n"
                "\n"
                "\n"
                "class Show:\n"
                "    def __init__(self, show_id: str, movie: 'Movie', screen: 'Screen', start_time: datetime):\n"
                "        self.show_id = show_id\n"
                "        self.movie = movie\n"
                "        self.screen = screen\n"
                "        self.start_time = start_time\n"
                "        self.seat_status: dict[str, SeatStatus] = {}  # seat_id -> status\n"
                "        self._lock = threading.Lock()\n"
                "\n"
                "    def get_available_seats(self) -> list[Seat]:\n"
                "        pass\n"
                "\n"
                "    def hold_seats(self, seat_ids: list[str], user_id: str) -> bool:\n"
                "        \"\"\"Atomically hold seats. Return False if any seat is unavailable.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def confirm_booking(self, seat_ids: list[str], user_id: str) -> 'Booking':\n"
                "        pass\n"
                "\n"
                "    def release_holds(self, seat_ids: list[str]) -> None:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Booking:\n"
                "    def __init__(self, booking_id: str, show: Show, seats: list[Seat], user_id: str, total: float):\n"
                "        self.booking_id = booking_id\n"
                "        self.show = show\n"
                "        self.seats = seats\n"
                "        self.user_id = user_id\n"
                "        self.total = total\n"
                "        self.booked_at = datetime.now()\n"
                "\n"
                "\n"
                "class BookingService:\n"
                "    def __init__(self):\n"
                "        self.shows: dict[str, Show] = {}\n"
                "        self.bookings: dict[str, Booking] = {}\n"
                "\n"
                "    def get_shows_for_movie(self, movie_id: str, city: str) -> list[Show]:\n"
                "        pass\n"
                "\n"
                "    def hold_seats(self, show_id: str, seat_ids: list[str], user_id: str) -> bool:\n"
                "        pass\n"
                "\n"
                "    def confirm_booking(self, show_id: str, seat_ids: list[str], user_id: str, payment: 'Payment') -> Booking:\n"
                "        pass\n"
                "\n"
                "    def cancel_booking(self, booking_id: str) -> bool:\n"
                "        pass\n"
            ),
            "java": (
                "public enum SeatType { SILVER, GOLD, PLATINUM }\n"
                "public enum SeatStatus { AVAILABLE, HELD, BOOKED }\n"
                "\n"
                "public class Seat {\n"
                "    private String seatId;\n"
                "    private String row;\n"
                "    private int number;\n"
                "    private SeatType type;\n"
                "}\n"
                "\n"
                "public class Show {\n"
                "    private String showId;\n"
                "    private Movie movie;\n"
                "    private Screen screen;\n"
                "    private LocalDateTime startTime;\n"
                "    private Map<String, SeatStatus> seatStatus;\n"
                "    private final ReentrantLock lock = new ReentrantLock();\n"
                "    public List<Seat> getAvailableSeats() { return null; }\n"
                "    public boolean holdSeats(List<String> seatIds, String userId) { return false; }\n"
                "    public Booking confirmBooking(List<String> seatIds, String userId) { return null; }\n"
                "}\n"
                "\n"
                "public class BookingService {\n"
                "    public List<Show> getShowsForMovie(String movieId, String city) { return null; }\n"
                "    public boolean holdSeats(String showId, List<String> seatIds, String userId) { return false; }\n"
                "    public Booking confirmBooking(String showId, List<String> seatIds, String userId) { return null; }\n"
                "    public boolean cancelBooking(String bookingId) { return false; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 8. Chess Game
    # -----------------------------------------------------------------------
    {
        "num": 8,
        "name": "Chess Game",
        "slug": "chess-game",
        "difficulty": "hard",
        "type": "lld",
        "description": (
            "Design an object-oriented chess game with full rules enforcement. "
            "Each piece type has distinct movement rules, the board validates legality "
            "of moves including check, checkmate, stalemate, castling, en passant, and "
            "pawn promotion. The system tracks game state and move history."
        ),
        "topics": ["oop", "design_patterns", "game_logic", "polymorphism"],
        "requirements": [
            "8x8 board with standard initial piece placement",
            "Each piece type (King, Queen, Rook, Bishop, Knight, Pawn) enforces its own movement rules",
            "Validate move legality: cannot move into check, must resolve check",
            "Detect check, checkmate, and stalemate conditions",
            "Support special moves: castling (king-side and queen-side), en passant, pawn promotion",
            "Track move history and support undo",
        ],
        "entities": [
            "Game", "Board", "Cell", "Piece", "King", "Queen",
            "Rook", "Bishop", "Knight", "Pawn", "Player",
            "Move", "MoveHistory", "Color",
        ],
        "design_patterns": ["Strategy", "Command", "Factory", "Observer"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "\n"
                "\n"
                "class Color(Enum):\n"
                "    WHITE = 1\n"
                "    BLACK = 2\n"
                "\n"
                "\n"
                "class Position:\n"
                "    def __init__(self, row: int, col: int):\n"
                "        self.row = row  # 0-7\n"
                "        self.col = col  # 0-7\n"
                "\n"
                "    def is_valid(self) -> bool:\n"
                "        return 0 <= self.row < 8 and 0 <= self.col < 8\n"
                "\n"
                "\n"
                "class Piece(ABC):\n"
                "    def __init__(self, color: Color, position: Position):\n"
                "        self.color = color\n"
                "        self.position = position\n"
                "        self.has_moved = False\n"
                "\n"
                "    @abstractmethod\n"
                "    def get_valid_moves(self, board: 'Board') -> list[Position]:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def symbol(self) -> str:\n"
                "        pass\n"
                "\n"
                "\n"
                "class King(Piece):\n"
                "    def get_valid_moves(self, board: 'Board') -> list[Position]:\n"
                "        pass\n"
                "\n"
                "    def symbol(self) -> str:\n"
                "        return 'K' if self.color == Color.WHITE else 'k'\n"
                "\n"
                "\n"
                "class Board:\n"
                "    def __init__(self):\n"
                "        self.grid: list[list[Piece | None]] = [[None] * 8 for _ in range(8)]\n"
                "\n"
                "    def setup_initial_position(self) -> None:\n"
                "        pass\n"
                "\n"
                "    def move_piece(self, start: Position, end: Position) -> bool:\n"
                "        pass\n"
                "\n"
                "    def is_in_check(self, color: Color) -> bool:\n"
                "        pass\n"
                "\n"
                "    def is_checkmate(self, color: Color) -> bool:\n"
                "        pass\n"
                "\n"
                "    def is_stalemate(self, color: Color) -> bool:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Game:\n"
                "    def __init__(self, white_player: 'Player', black_player: 'Player'):\n"
                "        self.board = Board()\n"
                "        self.board.setup_initial_position()\n"
                "        self.current_turn = Color.WHITE\n"
                "        self.move_history: list[tuple[Position, Position]] = []\n"
                "        self.is_over = False\n"
                "\n"
                "    def make_move(self, start: Position, end: Position) -> bool:\n"
                "        pass\n"
                "\n"
                "    def undo(self) -> bool:\n"
                "        pass\n"
            ),
            "java": (
                "public enum Color { WHITE, BLACK }\n"
                "\n"
                "public class Position {\n"
                "    private int row, col;\n"
                "    public boolean isValid() { return row >= 0 && row < 8 && col >= 0 && col < 8; }\n"
                "}\n"
                "\n"
                "public abstract class Piece {\n"
                "    protected Color color;\n"
                "    protected Position position;\n"
                "    protected boolean hasMoved;\n"
                "    public abstract List<Position> getValidMoves(Board board);\n"
                "    public abstract char symbol();\n"
                "}\n"
                "\n"
                "public class King extends Piece {\n"
                "    public List<Position> getValidMoves(Board board) { return null; }\n"
                "    public char symbol() { return color == Color.WHITE ? 'K' : 'k'; }\n"
                "}\n"
                "\n"
                "public class Board {\n"
                "    private Piece[][] grid = new Piece[8][8];\n"
                "    public void setupInitialPosition() {}\n"
                "    public boolean movePiece(Position start, Position end) { return false; }\n"
                "    public boolean isInCheck(Color color) { return false; }\n"
                "    public boolean isCheckmate(Color color) { return false; }\n"
                "}\n"
                "\n"
                "public class Game {\n"
                "    private Board board;\n"
                "    private Color currentTurn;\n"
                "    public boolean makeMove(Position start, Position end) { return false; }\n"
                "    public boolean undo() { return false; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 9. Snake and Ladder Game
    # -----------------------------------------------------------------------
    {
        "num": 9,
        "name": "Snake and Ladder Game",
        "slug": "snake-and-ladder-game",
        "difficulty": "easy",
        "type": "lld",
        "description": (
            "Design a Snake and Ladder board game for 2-4 players. The board has 100 cells "
            "with configurable snake and ladder positions. Players roll a die, move forward, "
            "and slide up ladders or down snakes. First player to reach cell 100 wins."
        ),
        "topics": ["oop", "design_patterns", "game_logic"],
        "requirements": [
            "100-cell board with configurable snakes (head -> tail) and ladders (bottom -> top)",
            "Support 2-4 players taking turns in order",
            "Roll a standard 6-sided die; move forward by the rolled amount",
            "If a player lands on a snake head, slide to the tail; if on ladder bottom, climb to top",
            "A player must roll the exact number to land on cell 100 (overshoot = stay)",
            "Detect winner (first to reach cell 100) and end the game",
        ],
        "entities": [
            "Game", "Board", "Cell", "Snake", "Ladder",
            "Player", "Dice",
        ],
        "design_patterns": ["Factory", "Template Method", "Observer"],
        "starter_code": {
            "python": (
                "import random\n"
                "\n"
                "\n"
                "class Dice:\n"
                "    def __init__(self, num_dice: int = 1, faces: int = 6):\n"
                "        self.num_dice = num_dice\n"
                "        self.faces = faces\n"
                "\n"
                "    def roll(self) -> int:\n"
                "        return sum(random.randint(1, self.faces) for _ in range(self.num_dice))\n"
                "\n"
                "\n"
                "class Player:\n"
                "    def __init__(self, name: str):\n"
                "        self.name = name\n"
                "        self.position = 0  # 0 = not on board, 1-100 = on board\n"
                "\n"
                "\n"
                "class Board:\n"
                "    def __init__(self, size: int = 100):\n"
                "        self.size = size\n"
                "        self.snakes: dict[int, int] = {}   # head -> tail\n"
                "        self.ladders: dict[int, int] = {}  # bottom -> top\n"
                "\n"
                "    def add_snake(self, head: int, tail: int) -> None:\n"
                "        pass\n"
                "\n"
                "    def add_ladder(self, bottom: int, top: int) -> None:\n"
                "        pass\n"
                "\n"
                "    def get_final_position(self, position: int) -> int:\n"
                "        \"\"\"Apply snake/ladder if applicable.\"\"\"\n"
                "        pass\n"
                "\n"
                "\n"
                "class Game:\n"
                "    def __init__(self, players: list[Player], board: Board, dice: Dice):\n"
                "        self.players = players\n"
                "        self.board = board\n"
                "        self.dice = dice\n"
                "        self.current_player_idx = 0\n"
                "        self.winner: Player | None = None\n"
                "\n"
                "    def play_turn(self) -> str:\n"
                "        \"\"\"Play one turn. Return description of what happened.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def is_over(self) -> bool:\n"
                "        return self.winner is not None\n"
                "\n"
                "    def play(self) -> Player:\n"
                "        \"\"\"Play full game and return winner.\"\"\"\n"
                "        pass\n"
            ),
            "java": (
                "public class Dice {\n"
                "    private int numDice, faces;\n"
                "    public int roll() { return 0; }\n"
                "}\n"
                "\n"
                "public class Player {\n"
                "    private String name;\n"
                "    private int position;\n"
                "}\n"
                "\n"
                "public class Board {\n"
                "    private int size;\n"
                "    private Map<Integer, Integer> snakes;\n"
                "    private Map<Integer, Integer> ladders;\n"
                "    public void addSnake(int head, int tail) {}\n"
                "    public void addLadder(int bottom, int top) {}\n"
                "    public int getFinalPosition(int position) { return position; }\n"
                "}\n"
                "\n"
                "public class Game {\n"
                "    private List<Player> players;\n"
                "    private Board board;\n"
                "    private Dice dice;\n"
                "    private Player winner;\n"
                "    public String playTurn() { return null; }\n"
                "    public boolean isOver() { return winner != null; }\n"
                "    public Player play() { return null; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 10. Tic-Tac-Toe
    # -----------------------------------------------------------------------
    {
        "num": 10,
        "name": "Tic-Tac-Toe",
        "slug": "tic-tac-toe",
        "difficulty": "easy",
        "type": "lld",
        "description": (
            "Design a Tic-Tac-Toe game supporting two players on an NxN board "
            "(classic 3x3 or generalized). Implement O(1) win detection using "
            "row/column/diagonal counters instead of brute-force board scanning. "
            "Support human vs human and human vs computer (minimax)."
        ),
        "topics": ["oop", "design_patterns", "game_logic", "algorithms"],
        "requirements": [
            "NxN board (default 3x3) with two players (X and O)",
            "Players alternate turns placing their mark on an empty cell",
            "Detect win (N in a row horizontally, vertically, or diagonally) in O(1) per move",
            "Detect draw when the board is full with no winner",
            "Support undo move and game reset",
            "Optional: AI player using minimax algorithm with alpha-beta pruning",
        ],
        "entities": [
            "Game", "Board", "Player", "HumanPlayer", "AIPlayer",
            "Cell", "Mark",
        ],
        "design_patterns": ["Strategy", "Factory", "Template Method"],
        "starter_code": {
            "python": (
                "from enum import Enum\n"
                "from abc import ABC, abstractmethod\n"
                "\n"
                "\n"
                "class Mark(Enum):\n"
                "    X = 'X'\n"
                "    O = 'O'\n"
                "    EMPTY = ' '\n"
                "\n"
                "\n"
                "class Board:\n"
                "    def __init__(self, size: int = 3):\n"
                "        self.size = size\n"
                "        self.grid = [[Mark.EMPTY] * size for _ in range(size)]\n"
                "        # O(1) win detection counters\n"
                "        self.row_counts = [{} for _ in range(size)]\n"
                "        self.col_counts = [{} for _ in range(size)]\n"
                "        self.diag_counts = [{}, {}]  # main diagonal, anti-diagonal\n"
                "\n"
                "    def place(self, row: int, col: int, mark: Mark) -> bool:\n"
                "        pass\n"
                "\n"
                "    def check_winner(self, row: int, col: int, mark: Mark) -> bool:\n"
                "        \"\"\"Check if placing mark at (row,col) wins. O(1).\"\"\"\n"
                "        pass\n"
                "\n"
                "    def is_full(self) -> bool:\n"
                "        pass\n"
                "\n"
                "    def undo(self, row: int, col: int) -> None:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Player(ABC):\n"
                "    def __init__(self, name: str, mark: Mark):\n"
                "        self.name = name\n"
                "        self.mark = mark\n"
                "\n"
                "    @abstractmethod\n"
                "    def get_move(self, board: Board) -> tuple[int, int]:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Game:\n"
                "    def __init__(self, player1: Player, player2: Player, board_size: int = 3):\n"
                "        self.board = Board(board_size)\n"
                "        self.players = [player1, player2]\n"
                "        self.current_idx = 0\n"
                "        self.winner: Player | None = None\n"
                "\n"
                "    def play_turn(self) -> str:\n"
                "        pass\n"
                "\n"
                "    def play(self) -> Player | None:\n"
                "        \"\"\"Play game to completion. Return winner or None for draw.\"\"\"\n"
                "        pass\n"
            ),
            "java": (
                "public enum Mark { X, O, EMPTY }\n"
                "\n"
                "public class Board {\n"
                "    private int size;\n"
                "    private Mark[][] grid;\n"
                "    public boolean place(int row, int col, Mark mark) { return false; }\n"
                "    public boolean checkWinner(int row, int col, Mark mark) { return false; }\n"
                "    public boolean isFull() { return false; }\n"
                "}\n"
                "\n"
                "public abstract class Player {\n"
                "    protected String name;\n"
                "    protected Mark mark;\n"
                "    public abstract int[] getMove(Board board);\n"
                "}\n"
                "\n"
                "public class Game {\n"
                "    private Board board;\n"
                "    private Player[] players;\n"
                "    private int currentIdx;\n"
                "    private Player winner;\n"
                "    public String playTurn() { return null; }\n"
                "    public Player play() { return null; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 11. In-Memory File System
    # -----------------------------------------------------------------------
    {
        "num": 11,
        "name": "In-Memory File System",
        "slug": "in-memory-file-system",
        "difficulty": "hard",
        "type": "lld",
        "description": (
            "Design an in-memory file system with files, directories, and a Unix-like "
            "path-based API. Support creating, reading, writing, and deleting files; "
            "creating and listing directories; and navigating with absolute/relative paths. "
            "Use the Composite pattern for the file/directory tree."
        ),
        "topics": ["oop", "design_patterns", "tree_structure", "composite_pattern"],
        "requirements": [
            "Create files and directories at arbitrary paths",
            "Read and write file contents (append and overwrite modes)",
            "List directory contents (ls) with optional recursive flag",
            "Delete files and directories (recursive delete for non-empty dirs)",
            "Move and copy files/directories",
            "Support path resolution (absolute /a/b/c and relative ../sibling)",
        ],
        "entities": [
            "FileSystem", "FSEntry", "File", "Directory",
            "Path", "Permissions",
        ],
        "design_patterns": ["Composite", "Iterator", "Factory"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from datetime import datetime\n"
                "\n"
                "\n"
                "class FSEntry(ABC):\n"
                "    def __init__(self, name: str, parent: 'Directory | None' = None):\n"
                "        self.name = name\n"
                "        self.parent = parent\n"
                "        self.created_at = datetime.now()\n"
                "        self.modified_at = datetime.now()\n"
                "\n"
                "    @abstractmethod\n"
                "    def size(self) -> int:\n"
                "        pass\n"
                "\n"
                "    def path(self) -> str:\n"
                "        \"\"\"Return absolute path like /a/b/c.\"\"\"\n"
                "        pass\n"
                "\n"
                "\n"
                "class File(FSEntry):\n"
                "    def __init__(self, name: str, parent: 'Directory | None' = None):\n"
                "        super().__init__(name, parent)\n"
                "        self.content = ''\n"
                "\n"
                "    def size(self) -> int:\n"
                "        return len(self.content)\n"
                "\n"
                "    def read(self) -> str:\n"
                "        pass\n"
                "\n"
                "    def write(self, content: str) -> None:\n"
                "        pass\n"
                "\n"
                "    def append(self, content: str) -> None:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Directory(FSEntry):\n"
                "    def __init__(self, name: str, parent: 'Directory | None' = None):\n"
                "        super().__init__(name, parent)\n"
                "        self.children: dict[str, FSEntry] = {}\n"
                "\n"
                "    def size(self) -> int:\n"
                "        return sum(child.size() for child in self.children.values())\n"
                "\n"
                "    def add(self, entry: FSEntry) -> None:\n"
                "        pass\n"
                "\n"
                "    def remove(self, name: str) -> FSEntry:\n"
                "        pass\n"
                "\n"
                "    def get(self, name: str) -> FSEntry | None:\n"
                "        pass\n"
                "\n"
                "    def list(self, recursive: bool = False) -> list[str]:\n"
                "        pass\n"
                "\n"
                "\n"
                "class FileSystem:\n"
                "    def __init__(self):\n"
                "        self.root = Directory('/')\n"
                "\n"
                "    def resolve(self, path: str) -> FSEntry | None:\n"
                "        \"\"\"Resolve an absolute path to an FSEntry.\"\"\"\n"
                "        pass\n"
                "\n"
                "    def mkdir(self, path: str) -> Directory:\n"
                "        pass\n"
                "\n"
                "    def create_file(self, path: str) -> File:\n"
                "        pass\n"
                "\n"
                "    def read_file(self, path: str) -> str:\n"
                "        pass\n"
                "\n"
                "    def write_file(self, path: str, content: str) -> None:\n"
                "        pass\n"
                "\n"
                "    def ls(self, path: str, recursive: bool = False) -> list[str]:\n"
                "        pass\n"
                "\n"
                "    def rm(self, path: str, recursive: bool = False) -> bool:\n"
                "        pass\n"
                "\n"
                "    def mv(self, src: str, dst: str) -> bool:\n"
                "        pass\n"
                "\n"
                "    def cp(self, src: str, dst: str) -> bool:\n"
                "        pass\n"
            ),
            "java": (
                "public abstract class FSEntry {\n"
                "    protected String name;\n"
                "    protected Directory parent;\n"
                "    protected LocalDateTime createdAt, modifiedAt;\n"
                "    public abstract int size();\n"
                "    public String path() { return null; }\n"
                "}\n"
                "\n"
                "public class File extends FSEntry {\n"
                "    private String content;\n"
                "    public int size() { return content.length(); }\n"
                "    public String read() { return content; }\n"
                "    public void write(String content) { this.content = content; }\n"
                "    public void append(String content) { this.content += content; }\n"
                "}\n"
                "\n"
                "public class Directory extends FSEntry {\n"
                "    private Map<String, FSEntry> children;\n"
                "    public int size() { return 0; }\n"
                "    public void add(FSEntry entry) {}\n"
                "    public FSEntry remove(String name) { return null; }\n"
                "    public List<String> list(boolean recursive) { return null; }\n"
                "}\n"
                "\n"
                "public class FileSystem {\n"
                "    private Directory root;\n"
                "    public FSEntry resolve(String path) { return null; }\n"
                "    public Directory mkdir(String path) { return null; }\n"
                "    public File createFile(String path) { return null; }\n"
                "    public String readFile(String path) { return null; }\n"
                "    public void writeFile(String path, String content) {}\n"
                "    public List<String> ls(String path, boolean recursive) { return null; }\n"
                "    public boolean rm(String path) { return false; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 12. Splitwise (Expense Sharing)
    # -----------------------------------------------------------------------
    {
        "num": 12,
        "name": "Splitwise - Expense Sharing",
        "slug": "splitwise-expense-sharing",
        "difficulty": "medium",
        "type": "lld",
        "description": (
            "Design an expense-sharing application like Splitwise. Users can create groups, "
            "add expenses with different split strategies (equal, exact, percentage), and "
            "the system calculates simplified debts so the minimum number of transactions "
            "settle all balances."
        ),
        "topics": ["oop", "design_patterns", "graph_algorithms", "finance"],
        "requirements": [
            "Users can create groups and add/remove members",
            "Add an expense paid by one user, split among a subset of the group",
            "Support split types: equal, exact amounts, percentage-based",
            "Track per-pair balances (A owes B $X)",
            "Simplify debts to minimize the number of settlement transactions (graph-based simplification)",
            "Show balance sheet per user: total owed, total owing, net balance",
        ],
        "entities": [
            "User", "Group", "Expense", "Split", "EqualSplit",
            "ExactSplit", "PercentSplit", "Balance", "Transaction",
            "ExpenseService",
        ],
        "design_patterns": ["Strategy", "Factory", "Observer"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "from collections import defaultdict\n"
                "\n"
                "\n"
                "class SplitType(Enum):\n"
                "    EQUAL = 1\n"
                "    EXACT = 2\n"
                "    PERCENT = 3\n"
                "\n"
                "\n"
                "class User:\n"
                "    def __init__(self, user_id: str, name: str, email: str):\n"
                "        self.user_id = user_id\n"
                "        self.name = name\n"
                "        self.email = email\n"
                "\n"
                "\n"
                "class Split(ABC):\n"
                "    @abstractmethod\n"
                "    def validate(self, total: float, participants: list[User]) -> bool:\n"
                "        pass\n"
                "\n"
                "    @abstractmethod\n"
                "    def get_shares(self, total: float, participants: list[User]) -> dict[str, float]:\n"
                "        \"\"\"Return {user_id: amount_owed}.\"\"\"\n"
                "        pass\n"
                "\n"
                "\n"
                "class EqualSplit(Split):\n"
                "    def validate(self, total: float, participants: list[User]) -> bool:\n"
                "        return len(participants) > 0\n"
                "\n"
                "    def get_shares(self, total: float, participants: list[User]) -> dict[str, float]:\n"
                "        pass\n"
                "\n"
                "\n"
                "class ExactSplit(Split):\n"
                "    def __init__(self, amounts: dict[str, float]):\n"
                "        self.amounts = amounts\n"
                "\n"
                "    def validate(self, total: float, participants: list[User]) -> bool:\n"
                "        return abs(sum(self.amounts.values()) - total) < 0.01\n"
                "\n"
                "    def get_shares(self, total: float, participants: list[User]) -> dict[str, float]:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Expense:\n"
                "    def __init__(self, expense_id: str, paid_by: User, amount: float,\n"
                "                 participants: list[User], split: Split, description: str):\n"
                "        self.expense_id = expense_id\n"
                "        self.paid_by = paid_by\n"
                "        self.amount = amount\n"
                "        self.participants = participants\n"
                "        self.split = split\n"
                "        self.description = description\n"
                "\n"
                "\n"
                "class ExpenseService:\n"
                "    def __init__(self):\n"
                "        self.balances: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))\n"
                "        self.expenses: list[Expense] = []\n"
                "\n"
                "    def add_expense(self, expense: Expense) -> None:\n"
                "        pass\n"
                "\n"
                "    def get_balance(self, user_id: str) -> dict[str, float]:\n"
                "        \"\"\"Return {other_user_id: net_amount} (positive = they owe you).\"\"\"\n"
                "        pass\n"
                "\n"
                "    def simplify_debts(self, group_user_ids: list[str]) -> list[tuple[str, str, float]]:\n"
                "        \"\"\"Return minimal settlement: [(payer_id, payee_id, amount)].\"\"\"\n"
                "        pass\n"
            ),
            "java": (
                "public enum SplitType { EQUAL, EXACT, PERCENT }\n"
                "\n"
                "public class User {\n"
                "    private String userId, name, email;\n"
                "}\n"
                "\n"
                "public abstract class Split {\n"
                "    public abstract boolean validate(double total, List<User> participants);\n"
                "    public abstract Map<String, Double> getShares(double total, List<User> participants);\n"
                "}\n"
                "\n"
                "public class EqualSplit extends Split {\n"
                "    public boolean validate(double total, List<User> participants) { return true; }\n"
                "    public Map<String, Double> getShares(double total, List<User> participants) { return null; }\n"
                "}\n"
                "\n"
                "public class Expense {\n"
                "    private String expenseId;\n"
                "    private User paidBy;\n"
                "    private double amount;\n"
                "    private List<User> participants;\n"
                "    private Split split;\n"
                "}\n"
                "\n"
                "public class ExpenseService {\n"
                "    private Map<String, Map<String, Double>> balances;\n"
                "    public void addExpense(Expense expense) {}\n"
                "    public Map<String, Double> getBalance(String userId) { return null; }\n"
                "    public List<String[]> simplifyDebts(List<String> userIds) { return null; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 13. Online Shopping Cart
    # -----------------------------------------------------------------------
    {
        "num": 13,
        "name": "Online Shopping Cart",
        "slug": "online-shopping-cart",
        "difficulty": "medium",
        "type": "lld",
        "description": (
            "Design an e-commerce shopping cart system that manages a product catalog, "
            "user carts, inventory tracking, checkout with multiple payment methods, "
            "and order placement. Apply the Strategy pattern for discount/pricing rules "
            "and Observer pattern for inventory alerts."
        ),
        "topics": ["oop", "design_patterns", "e_commerce", "state_management"],
        "requirements": [
            "Product catalog with categories, prices, and stock quantities",
            "Add/remove/update items in a user's cart with quantity validation against inventory",
            "Apply discount strategies: percentage off, flat amount off, buy-X-get-Y-free",
            "Checkout flow: validate stock -> apply discounts -> select payment -> place order",
            "Deduct inventory on successful order; restore on cancellation",
            "Order lifecycle: PLACED -> PAID -> SHIPPED -> DELIVERED (or CANCELLED)",
        ],
        "entities": [
            "Product", "Category", "CartItem", "ShoppingCart",
            "Order", "OrderStatus", "OrderItem", "Payment",
            "PaymentMethod", "DiscountStrategy", "Inventory",
            "User", "Address",
        ],
        "design_patterns": ["Strategy", "Observer", "Factory", "Builder"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "from datetime import datetime\n"
                "\n"
                "\n"
                "class OrderStatus(Enum):\n"
                "    PLACED = 1\n"
                "    PAID = 2\n"
                "    SHIPPED = 3\n"
                "    DELIVERED = 4\n"
                "    CANCELLED = 5\n"
                "\n"
                "\n"
                "class Product:\n"
                "    def __init__(self, product_id: str, name: str, price: float, stock: int, category: str):\n"
                "        self.product_id = product_id\n"
                "        self.name = name\n"
                "        self.price = price\n"
                "        self.stock = stock\n"
                "        self.category = category\n"
                "\n"
                "\n"
                "class CartItem:\n"
                "    def __init__(self, product: Product, quantity: int):\n"
                "        self.product = product\n"
                "        self.quantity = quantity\n"
                "\n"
                "    def subtotal(self) -> float:\n"
                "        return self.product.price * self.quantity\n"
                "\n"
                "\n"
                "class DiscountStrategy(ABC):\n"
                "    @abstractmethod\n"
                "    def apply(self, items: list[CartItem]) -> float:\n"
                "        \"\"\"Return discount amount.\"\"\"\n"
                "        pass\n"
                "\n"
                "\n"
                "class ShoppingCart:\n"
                "    def __init__(self, user_id: str):\n"
                "        self.user_id = user_id\n"
                "        self.items: dict[str, CartItem] = {}  # product_id -> CartItem\n"
                "\n"
                "    def add_item(self, product: Product, quantity: int) -> bool:\n"
                "        pass\n"
                "\n"
                "    def remove_item(self, product_id: str) -> bool:\n"
                "        pass\n"
                "\n"
                "    def update_quantity(self, product_id: str, quantity: int) -> bool:\n"
                "        pass\n"
                "\n"
                "    def get_total(self, discount: DiscountStrategy = None) -> float:\n"
                "        pass\n"
                "\n"
                "    def clear(self) -> None:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Order:\n"
                "    def __init__(self, order_id: str, user_id: str, items: list[CartItem], total: float):\n"
                "        self.order_id = order_id\n"
                "        self.user_id = user_id\n"
                "        self.items = items\n"
                "        self.total = total\n"
                "        self.status = OrderStatus.PLACED\n"
                "        self.created_at = datetime.now()\n"
                "\n"
                "    def cancel(self) -> bool:\n"
                "        pass\n"
                "\n"
                "\n"
                "class OrderService:\n"
                "    def __init__(self):\n"
                "        self.orders: dict[str, Order] = {}\n"
                "\n"
                "    def checkout(self, cart: ShoppingCart, discount: DiscountStrategy = None) -> Order:\n"
                "        pass\n"
                "\n"
                "    def cancel_order(self, order_id: str) -> bool:\n"
                "        pass\n"
            ),
            "java": (
                "public enum OrderStatus { PLACED, PAID, SHIPPED, DELIVERED, CANCELLED }\n"
                "\n"
                "public class Product {\n"
                "    private String productId, name, category;\n"
                "    private double price;\n"
                "    private int stock;\n"
                "}\n"
                "\n"
                "public class CartItem {\n"
                "    private Product product;\n"
                "    private int quantity;\n"
                "    public double subtotal() { return product.getPrice() * quantity; }\n"
                "}\n"
                "\n"
                "public interface DiscountStrategy {\n"
                "    double apply(List<CartItem> items);\n"
                "}\n"
                "\n"
                "public class ShoppingCart {\n"
                "    private String userId;\n"
                "    private Map<String, CartItem> items;\n"
                "    public boolean addItem(Product product, int qty) { return false; }\n"
                "    public boolean removeItem(String productId) { return false; }\n"
                "    public double getTotal(DiscountStrategy discount) { return 0; }\n"
                "    public void clear() {}\n"
                "}\n"
                "\n"
                "public class Order {\n"
                "    private String orderId, userId;\n"
                "    private List<CartItem> items;\n"
                "    private double total;\n"
                "    private OrderStatus status;\n"
                "    public boolean cancel() { return false; }\n"
                "}\n"
                "\n"
                "public class OrderService {\n"
                "    public Order checkout(ShoppingCart cart, DiscountStrategy discount) { return null; }\n"
                "    public boolean cancelOrder(String orderId) { return false; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 14. Stack Overflow (Q&A Platform)
    # -----------------------------------------------------------------------
    {
        "num": 14,
        "name": "Stack Overflow - Q&A Platform",
        "slug": "stack-overflow-qa-platform",
        "difficulty": "hard",
        "type": "lld",
        "description": (
            "Design a Q&A platform like Stack Overflow with questions, answers, comments, "
            "voting, tagging, reputation system, and moderation. Users earn reputation "
            "through upvotes and can unlock privileges at thresholds. The system uses "
            "the Observer pattern for notifications and Strategy for ranking."
        ),
        "topics": ["oop", "design_patterns", "reputation_systems", "search"],
        "requirements": [
            "Users can post questions with tags, post answers, and add comments",
            "Upvote/downvote questions and answers (+10 rep for question upvote, +15 for answer upvote, -2 for downvote received)",
            "Mark an answer as accepted (+15 rep for answerer, +2 for questioner)",
            "Tag system: questions have 1-5 tags; support tag-based search and filtering",
            "Reputation-gated privileges: vote (15+), comment (50+), edit (2000+), close (3000+)",
            "Sort answers by votes, newest, or activity; search questions by keyword + tags",
        ],
        "entities": [
            "User", "Question", "Answer", "Comment", "Vote",
            "Tag", "Reputation", "Badge", "Notification",
            "SearchService", "ModerationAction",
        ],
        "design_patterns": ["Observer", "Strategy", "Factory", "Decorator"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from enum import Enum\n"
                "from datetime import datetime\n"
                "\n"
                "\n"
                "class VoteType(Enum):\n"
                "    UPVOTE = 1\n"
                "    DOWNVOTE = -1\n"
                "\n"
                "\n"
                "class User:\n"
                "    def __init__(self, user_id: str, username: str, email: str):\n"
                "        self.user_id = user_id\n"
                "        self.username = username\n"
                "        self.email = email\n"
                "        self.reputation = 1\n"
                "        self.questions: list['Question'] = []\n"
                "        self.answers: list['Answer'] = []\n"
                "\n"
                "    def can_vote(self) -> bool:\n"
                "        return self.reputation >= 15\n"
                "\n"
                "    def can_comment(self) -> bool:\n"
                "        return self.reputation >= 50\n"
                "\n"
                "    def can_edit(self) -> bool:\n"
                "        return self.reputation >= 2000\n"
                "\n"
                "\n"
                "class Votable(ABC):\n"
                "    def __init__(self):\n"
                "        self.votes: dict[str, VoteType] = {}  # user_id -> vote\n"
                "\n"
                "    def vote(self, user: User, vote_type: VoteType) -> bool:\n"
                "        pass\n"
                "\n"
                "    def score(self) -> int:\n"
                "        return sum(v.value for v in self.votes.values())\n"
                "\n"
                "\n"
                "class Question(Votable):\n"
                "    def __init__(self, question_id: str, title: str, body: str, author: User, tags: list[str]):\n"
                "        super().__init__()\n"
                "        self.question_id = question_id\n"
                "        self.title = title\n"
                "        self.body = body\n"
                "        self.author = author\n"
                "        self.tags = tags\n"
                "        self.answers: list['Answer'] = []\n"
                "        self.comments: list['Comment'] = []\n"
                "        self.accepted_answer: 'Answer | None' = None\n"
                "        self.created_at = datetime.now()\n"
                "\n"
                "    def add_answer(self, answer: 'Answer') -> None:\n"
                "        pass\n"
                "\n"
                "    def accept_answer(self, answer: 'Answer') -> None:\n"
                "        pass\n"
                "\n"
                "\n"
                "class Answer(Votable):\n"
                "    def __init__(self, answer_id: str, body: str, author: User, question: Question):\n"
                "        super().__init__()\n"
                "        self.answer_id = answer_id\n"
                "        self.body = body\n"
                "        self.author = author\n"
                "        self.question = question\n"
                "        self.is_accepted = False\n"
                "        self.comments: list['Comment'] = []\n"
                "        self.created_at = datetime.now()\n"
                "\n"
                "\n"
                "class QAService:\n"
                "    def __init__(self):\n"
                "        self.questions: dict[str, Question] = {}\n"
                "        self.users: dict[str, User] = {}\n"
                "\n"
                "    def post_question(self, user: User, title: str, body: str, tags: list[str]) -> Question:\n"
                "        pass\n"
                "\n"
                "    def post_answer(self, user: User, question_id: str, body: str) -> Answer:\n"
                "        pass\n"
                "\n"
                "    def vote(self, user: User, target_id: str, vote_type: VoteType) -> bool:\n"
                "        pass\n"
                "\n"
                "    def search(self, query: str, tags: list[str] = None) -> list[Question]:\n"
                "        pass\n"
            ),
            "java": (
                "public enum VoteType { UPVOTE(1), DOWNVOTE(-1);\n"
                "    private final int value;\n"
                "    VoteType(int v) { this.value = v; }\n"
                "    public int getValue() { return value; }\n"
                "}\n"
                "\n"
                "public class User {\n"
                "    private String userId, username, email;\n"
                "    private int reputation = 1;\n"
                "    public boolean canVote() { return reputation >= 15; }\n"
                "    public boolean canComment() { return reputation >= 50; }\n"
                "}\n"
                "\n"
                "public abstract class Votable {\n"
                "    protected Map<String, VoteType> votes;\n"
                "    public boolean vote(User user, VoteType type) { return false; }\n"
                "    public int score() { return 0; }\n"
                "}\n"
                "\n"
                "public class Question extends Votable {\n"
                "    private String questionId, title, body;\n"
                "    private User author;\n"
                "    private List<String> tags;\n"
                "    private List<Answer> answers;\n"
                "    private Answer acceptedAnswer;\n"
                "    public void addAnswer(Answer answer) {}\n"
                "    public void acceptAnswer(Answer answer) {}\n"
                "}\n"
                "\n"
                "public class Answer extends Votable {\n"
                "    private String answerId, body;\n"
                "    private User author;\n"
                "    private Question question;\n"
                "    private boolean isAccepted;\n"
                "}\n"
                "\n"
                "public class QAService {\n"
                "    public Question postQuestion(User user, String title, String body, List<String> tags) { return null; }\n"
                "    public Answer postAnswer(User user, String questionId, String body) { return null; }\n"
                "    public boolean vote(User user, String targetId, VoteType type) { return false; }\n"
                "    public List<Question> search(String query, List<String> tags) { return null; }\n"
                "}\n"
            ),
        },
    },
    # -----------------------------------------------------------------------
    # 15. Rate Limiter (LLD)
    # -----------------------------------------------------------------------
    {
        "num": 15,
        "name": "Rate Limiter (LLD)",
        "slug": "rate-limiter-lld",
        "difficulty": "medium",
        "type": "lld",
        "description": (
            "Design and implement a rate limiter at the class/component level "
            "(not the distributed system level). Implement multiple algorithms "
            "(Token Bucket, Sliding Window Log, Sliding Window Counter, Fixed Window) "
            "behind a common interface. The limiter decides allow/deny per client-key "
            "and returns appropriate metadata (remaining tokens, retry-after)."
        ),
        "topics": ["oop", "design_patterns", "algorithms", "concurrency"],
        "requirements": [
            "Common RateLimiter interface: allow(client_key) -> RateLimitResult",
            "Implement Token Bucket: configurable rate (tokens/sec) and burst capacity",
            "Implement Sliding Window Log: track exact timestamps, count within window",
            "Implement Sliding Window Counter: hybrid of fixed window + proportional overlap",
            "Implement Fixed Window Counter: simple count per discrete time window",
            "Thread-safe: concurrent calls for the same client key must not corrupt state",
            "Return metadata: allowed (bool), remaining quota, retry-after seconds",
        ],
        "entities": [
            "RateLimiter", "TokenBucketLimiter", "SlidingWindowLogLimiter",
            "SlidingWindowCounterLimiter", "FixedWindowLimiter",
            "RateLimitResult", "RateLimitConfig",
        ],
        "design_patterns": ["Strategy", "Factory", "Template Method"],
        "starter_code": {
            "python": (
                "from abc import ABC, abstractmethod\n"
                "from dataclasses import dataclass\n"
                "from time import time\n"
                "import threading\n"
                "\n"
                "\n"
                "@dataclass\n"
                "class RateLimitResult:\n"
                "    allowed: bool\n"
                "    remaining: int\n"
                "    retry_after: float  # seconds until next allowed request; 0 if allowed\n"
                "\n"
                "\n"
                "class RateLimiter(ABC):\n"
                "    @abstractmethod\n"
                "    def allow(self, client_key: str) -> RateLimitResult:\n"
                "        pass\n"
                "\n"
                "\n"
                "class TokenBucketLimiter(RateLimiter):\n"
                "    def __init__(self, rate: float, capacity: int):\n"
                "        \"\"\"\n"
                "        rate: tokens refilled per second\n"
                "        capacity: max burst size\n"
                "        \"\"\"\n"
                "        self.rate = rate\n"
                "        self.capacity = capacity\n"
                "        self._buckets: dict[str, dict] = {}  # client_key -> {tokens, last_refill}\n"
                "        self._lock = threading.Lock()\n"
                "\n"
                "    def allow(self, client_key: str) -> RateLimitResult:\n"
                "        pass\n"
                "\n"
                "\n"
                "class SlidingWindowLogLimiter(RateLimiter):\n"
                "    def __init__(self, max_requests: int, window_seconds: float):\n"
                "        self.max_requests = max_requests\n"
                "        self.window_seconds = window_seconds\n"
                "        self._logs: dict[str, list[float]] = {}  # client_key -> [timestamps]\n"
                "        self._lock = threading.Lock()\n"
                "\n"
                "    def allow(self, client_key: str) -> RateLimitResult:\n"
                "        pass\n"
                "\n"
                "\n"
                "class FixedWindowLimiter(RateLimiter):\n"
                "    def __init__(self, max_requests: int, window_seconds: float):\n"
                "        self.max_requests = max_requests\n"
                "        self.window_seconds = window_seconds\n"
                "        self._windows: dict[str, dict] = {}  # client_key -> {window_start, count}\n"
                "        self._lock = threading.Lock()\n"
                "\n"
                "    def allow(self, client_key: str) -> RateLimitResult:\n"
                "        pass\n"
                "\n"
                "\n"
                "class RateLimiterFactory:\n"
                "    @staticmethod\n"
                "    def create(algorithm: str, **kwargs) -> RateLimiter:\n"
                "        if algorithm == 'token_bucket':\n"
                "            return TokenBucketLimiter(kwargs['rate'], kwargs['capacity'])\n"
                "        elif algorithm == 'sliding_window_log':\n"
                "            return SlidingWindowLogLimiter(kwargs['max_requests'], kwargs['window_seconds'])\n"
                "        elif algorithm == 'fixed_window':\n"
                "            return FixedWindowLimiter(kwargs['max_requests'], kwargs['window_seconds'])\n"
                "        raise ValueError(f'Unknown algorithm: {algorithm}')\n"
            ),
            "java": (
                "public class RateLimitResult {\n"
                "    private boolean allowed;\n"
                "    private int remaining;\n"
                "    private double retryAfter;\n"
                "}\n"
                "\n"
                "public interface RateLimiter {\n"
                "    RateLimitResult allow(String clientKey);\n"
                "}\n"
                "\n"
                "public class TokenBucketLimiter implements RateLimiter {\n"
                "    private double rate;\n"
                "    private int capacity;\n"
                "    private ConcurrentHashMap<String, double[]> buckets;\n"
                "    public TokenBucketLimiter(double rate, int capacity) {}\n"
                "    public synchronized RateLimitResult allow(String clientKey) { return null; }\n"
                "}\n"
                "\n"
                "public class SlidingWindowLogLimiter implements RateLimiter {\n"
                "    private int maxRequests;\n"
                "    private double windowSeconds;\n"
                "    private ConcurrentHashMap<String, List<Long>> logs;\n"
                "    public SlidingWindowLogLimiter(int maxRequests, double windowSeconds) {}\n"
                "    public synchronized RateLimitResult allow(String clientKey) { return null; }\n"
                "}\n"
                "\n"
                "public class FixedWindowLimiter implements RateLimiter {\n"
                "    private int maxRequests;\n"
                "    private double windowSeconds;\n"
                "    public FixedWindowLimiter(int maxRequests, double windowSeconds) {}\n"
                "    public synchronized RateLimitResult allow(String clientKey) { return null; }\n"
                "}\n"
                "\n"
                "public class RateLimiterFactory {\n"
                "    public static RateLimiter create(String algorithm, Map<String, Object> config) { return null; }\n"
                "}\n"
            ),
        },
    },
]

# ---------------------------------------------------------------------------
# 7 LLD Teaching Plans
# ---------------------------------------------------------------------------

LLD_TEACHING_PLANS = {
    # -----------------------------------------------------------------------
    # 1. OOP Principles
    # -----------------------------------------------------------------------
    "oop-principles": {
        "title": "OOP Principles",
        "topic": "OOP Principles",
        "introduction": (
            "Object-Oriented Programming is the foundation of Low-Level Design.  "
            "The four pillars -- Encapsulation, Inheritance, Polymorphism, and Abstraction -- "
            "are not just vocabulary words; they are design levers.  Encapsulation hides internal "
            "state behind a well-defined interface so clients cannot corrupt invariants.  "
            "Inheritance creates an is-a hierarchy for code reuse, but must be used judiciously "
            "(prefer composition over inheritance when the relationship is has-a).  Polymorphism "
            "lets you write code against an interface and swap implementations at runtime.  "
            "Abstraction focuses on *what* an object does, not *how* -- defining contracts that "
            "decouple modules."
        ),
        "key_ideas": [
            "Encapsulation: bundle data + behavior; expose only what clients need (private fields, public methods)",
            "Inheritance: is-a relationship; derived classes extend base class behavior. Beware deep hierarchies.",
            "Polymorphism: one interface, multiple implementations. Method overriding (runtime) vs overloading (compile-time).",
            "Abstraction: abstract classes and interfaces define contracts. Clients depend on abstractions, not concretions.",
            "Composition over Inheritance: has-a relationships are more flexible; inject behavior via strategy objects instead of subclassing.",
            "Access modifiers: public, protected, private -- control visibility to enforce encapsulation.",
        ],
        "canonical_problems": [
            {"name": "Parking Lot System", "slug": "parking-lot-system", "difficulty": "medium",
             "why": "Vehicle hierarchy (Car, Motorcycle, Truck) demonstrates inheritance and polymorphism; PricingStrategy shows abstraction"},
            {"name": "Library Management System", "slug": "library-management-system", "difficulty": "easy",
             "why": "Book vs BookItem illustrates composition; Member encapsulates borrowing rules behind clean methods"},
            {"name": "Chess Game", "slug": "chess-game", "difficulty": "hard",
             "why": "Piece hierarchy with abstract get_valid_moves() is textbook polymorphism; Board encapsulates game state"},
        ],
        "common_mistakes": [
            "Making everything public 'for convenience' -- destroys encapsulation",
            "Deep inheritance chains (>3 levels) that are fragile and hard to understand",
            "Using inheritance when composition would be cleaner (e.g., a Duck that also Swims)",
            "Confusing abstraction with abstract classes -- abstraction is a design principle, abstract classes are a mechanism",
            "Violating encapsulation by exposing mutable internal collections (return a copy instead)",
        ],
        "visual_examples": [
            {
                "description": "Vehicle class hierarchy showing inheritance and polymorphism",
                "mermaid": (
                    "classDiagram\n"
                    "    class Vehicle {\n"
                    "        <<abstract>>\n"
                    "        +String licensePlate\n"
                    "        +VehicleType type\n"
                    "        +getType() VehicleType\n"
                    "    }\n"
                    "    class Car {\n"
                    "        +getType() VehicleType\n"
                    "    }\n"
                    "    class Motorcycle {\n"
                    "        +getType() VehicleType\n"
                    "    }\n"
                    "    class Truck {\n"
                    "        +getType() VehicleType\n"
                    "    }\n"
                    "    Vehicle <|-- Car\n"
                    "    Vehicle <|-- Motorcycle\n"
                    "    Vehicle <|-- Truck"
                ),
            },
            {
                "description": "Composition vs Inheritance: ParkingLot HAS-A PricingStrategy (injected), not IS-A",
                "mermaid": (
                    "classDiagram\n"
                    "    class ParkingLot {\n"
                    "        -PricingStrategy pricing\n"
                    "        +park(Vehicle) Ticket\n"
                    "        +unpark(Ticket) float\n"
                    "    }\n"
                    "    class PricingStrategy {\n"
                    "        <<interface>>\n"
                    "        +calculateFee(entry, exit, type) float\n"
                    "    }\n"
                    "    class HourlyPricing {\n"
                    "        +calculateFee() float\n"
                    "    }\n"
                    "    class TieredPricing {\n"
                    "        +calculateFee() float\n"
                    "    }\n"
                    "    ParkingLot --> PricingStrategy\n"
                    "    PricingStrategy <|.. HourlyPricing\n"
                    "    PricingStrategy <|.. TieredPricing"
                ),
            },
        ],
    },
    # -----------------------------------------------------------------------
    # 2. SOLID Principles
    # -----------------------------------------------------------------------
    "solid-principles": {
        "title": "SOLID Principles",
        "topic": "SOLID Principles",
        "introduction": (
            "SOLID is a set of five design principles that make object-oriented systems "
            "easier to understand, maintain, and extend.  They were popularized by Robert C. Martin "
            "and form the backbone of clean architecture.  Each principle addresses a specific axis "
            "of change: S controls the scope of a class, O controls how you extend behavior, "
            "L ensures substitutability, I prevents bloated interfaces, and D inverts the "
            "dependency direction so high-level policy does not depend on low-level detail."
        ),
        "key_ideas": [
            "Single Responsibility (SRP): A class should have one reason to change. If a class handles both parking logic AND payment processing, split it.",
            "Open/Closed (OCP): Open for extension, closed for modification. Add new behavior by creating new classes (e.g., new PricingStrategy), not editing existing ones.",
            "Liskov Substitution (LSP): Subtypes must be substitutable for their base types. If Square extends Rectangle but breaks setWidth/setHeight semantics, LSP is violated.",
            "Interface Segregation (ISP): No client should depend on methods it doesn't use. Split fat interfaces into focused ones (e.g., Printable, Scannable, Faxable instead of one Machine interface).",
            "Dependency Inversion (DIP): High-level modules depend on abstractions, not concretions. ParkingLot depends on PricingStrategy interface, not HourlyPricing directly.",
        ],
        "canonical_problems": [
            {"name": "Parking Lot System", "slug": "parking-lot-system", "difficulty": "medium",
             "why": "PricingStrategy (OCP+DIP), separate ParkingSpot vs ParkingFloor vs ParkingLot (SRP), Vehicle subtypes (LSP)"},
            {"name": "Vending Machine", "slug": "vending-machine", "difficulty": "easy",
             "why": "State pattern (OCP -- add states without modifying machine), separate Inventory from Payment (SRP)"},
            {"name": "Online Shopping Cart", "slug": "online-shopping-cart", "difficulty": "medium",
             "why": "DiscountStrategy (OCP+DIP), separate Cart from Order from Payment (SRP), PaymentMethod interface (ISP)"},
        ],
        "common_mistakes": [
            "God classes that do everything (violates SRP) -- split by axis of change",
            "Modifying existing switch/case blocks to add new types instead of using polymorphism (violates OCP)",
            "Square-Rectangle problem: overriding setters in a way that violates parent's contract (LSP)",
            "One massive interface that forces implementors to stub out methods they don't need (ISP)",
            "High-level business logic importing concrete database classes instead of depending on a repository interface (DIP)",
        ],
        "visual_examples": [
            {
                "description": "SRP violation vs fix: a monolithic ParkingService split into focused classes",
                "mermaid": (
                    "classDiagram\n"
                    "    class ParkingService_BAD {\n"
                    "        +park()\n"
                    "        +unpark()\n"
                    "        +calculateFee()\n"
                    "        +sendNotification()\n"
                    "        +generateReport()\n"
                    "    }\n"
                    "    note for ParkingService_BAD \"Violates SRP: 3 reasons to change\"\n"
                    "    class ParkingManager {\n"
                    "        +park()\n"
                    "        +unpark()\n"
                    "    }\n"
                    "    class FeeCalculator {\n"
                    "        +calculateFee()\n"
                    "    }\n"
                    "    class NotificationService {\n"
                    "        +sendNotification()\n"
                    "    }\n"
                    "    ParkingManager --> FeeCalculator\n"
                    "    ParkingManager --> NotificationService"
                ),
            },
            {
                "description": "OCP + DIP: adding new discount types without modifying existing code",
                "mermaid": (
                    "classDiagram\n"
                    "    class OrderService {\n"
                    "        -DiscountStrategy discount\n"
                    "        +checkout(cart) Order\n"
                    "    }\n"
                    "    class DiscountStrategy {\n"
                    "        <<interface>>\n"
                    "        +apply(items) float\n"
                    "    }\n"
                    "    class PercentDiscount {\n"
                    "        +apply(items) float\n"
                    "    }\n"
                    "    class FlatDiscount {\n"
                    "        +apply(items) float\n"
                    "    }\n"
                    "    class BuyXGetYFree {\n"
                    "        +apply(items) float\n"
                    "    }\n"
                    "    OrderService --> DiscountStrategy\n"
                    "    DiscountStrategy <|.. PercentDiscount\n"
                    "    DiscountStrategy <|.. FlatDiscount\n"
                    "    DiscountStrategy <|.. BuyXGetYFree"
                ),
            },
        ],
    },
    # -----------------------------------------------------------------------
    # 3. Creational Design Patterns
    # -----------------------------------------------------------------------
    "design-patterns-creational": {
        "title": "Creational Design Patterns",
        "topic": "Creational Design Patterns",
        "introduction": (
            "Creational patterns deal with object creation mechanisms -- they abstract the "
            "instantiation process so the system is independent of how objects are created, "
            "composed, and represented.  In LLD interviews, Factory and Builder appear most "
            "often.  Factory Method lets a class defer instantiation to subclasses (or a static "
            "method).  Abstract Factory creates families of related objects.  Builder separates "
            "construction of a complex object from its representation (useful when constructors "
            "have many optional parameters).  Singleton ensures a class has exactly one instance.  "
            "Prototype creates new objects by cloning an existing one."
        ),
        "key_ideas": [
            "Factory Method: define an interface for creating an object, but let subclasses decide which class to instantiate. Eliminates switch/case on type.",
            "Abstract Factory: a factory of factories -- creates families of related objects (e.g., UIFactory producing Button+Checkbox for Windows or Mac).",
            "Builder: step-by-step construction of complex objects. Separates construction from representation. Fluent interface (method chaining).",
            "Singleton: exactly one instance, globally accessible. Use sparingly -- often a sign of hidden global state. Thread-safe variants matter.",
            "Prototype: create objects by cloning a prototype. Useful when object creation is expensive (e.g., deep copy of a complex graph).",
        ],
        "canonical_problems": [
            {"name": "Parking Lot System", "slug": "parking-lot-system", "difficulty": "medium",
             "why": "VehicleFactory creates Car/Motorcycle/Truck; ParkingLot is a Singleton; Builder for configuring floors"},
            {"name": "Vending Machine", "slug": "vending-machine", "difficulty": "easy",
             "why": "Singleton VendingMachine; Factory for creating State objects based on current context"},
            {"name": "Hotel Booking System", "slug": "hotel-booking-system", "difficulty": "medium",
             "why": "Builder pattern for constructing Reservation with many optional fields (services, special requests, room preferences)"},
        ],
        "common_mistakes": [
            "Overusing Singleton -- it introduces global state and makes testing difficult (cannot mock easily)",
            "Factory that returns concrete types instead of interfaces (defeats the purpose of abstraction)",
            "Builder without validation -- build() should verify required fields are set",
            "Confusing Factory Method (inheritance-based) with Simple Factory (static method) -- both are valid, but have different trade-offs",
            "Not making Singleton thread-safe in concurrent environments (double-checked locking or inner-class holder pattern in Java)",
        ],
        "visual_examples": [
            {
                "description": "Factory Method: VehicleFactory creates different vehicle types",
                "mermaid": (
                    "classDiagram\n"
                    "    class VehicleFactory {\n"
                    "        +create(type, plate) Vehicle\n"
                    "    }\n"
                    "    class Vehicle {\n"
                    "        <<abstract>>\n"
                    "    }\n"
                    "    class Car\n"
                    "    class Motorcycle\n"
                    "    class Truck\n"
                    "    VehicleFactory ..> Vehicle : creates\n"
                    "    Vehicle <|-- Car\n"
                    "    Vehicle <|-- Motorcycle\n"
                    "    Vehicle <|-- Truck"
                ),
            },
            {
                "description": "Builder: step-by-step construction of a Reservation",
                "mermaid": (
                    "classDiagram\n"
                    "    class ReservationBuilder {\n"
                    "        +setGuest(Guest) ReservationBuilder\n"
                    "        +setRoom(Room) ReservationBuilder\n"
                    "        +setDates(in, out) ReservationBuilder\n"
                    "        +addService(Service) ReservationBuilder\n"
                    "        +build() Reservation\n"
                    "    }\n"
                    "    class Reservation {\n"
                    "        -Guest guest\n"
                    "        -Room room\n"
                    "        -Date checkIn\n"
                    "        -Date checkOut\n"
                    "        -List~Service~ services\n"
                    "    }\n"
                    "    ReservationBuilder ..> Reservation : builds"
                ),
            },
        ],
    },
    # -----------------------------------------------------------------------
    # 4. Structural Design Patterns
    # -----------------------------------------------------------------------
    "design-patterns-structural": {
        "title": "Structural Design Patterns",
        "topic": "Structural Design Patterns",
        "introduction": (
            "Structural patterns are about composing classes and objects into larger structures "
            "while keeping them flexible and efficient.  Adapter converts one interface to another "
            "so incompatible classes can work together.  Decorator adds responsibilities to objects "
            "dynamically without subclassing.  Composite lets you treat individual objects and "
            "compositions uniformly (tree structures).  Facade provides a simplified interface to "
            "a complex subsystem.  Proxy controls access to an object (lazy loading, access control, "
            "logging).  Bridge separates an abstraction from its implementation so both can vary "
            "independently."
        ),
        "key_ideas": [
            "Adapter: wraps an incompatible class to make it work with an expected interface. Real-world: power adapters, XML-to-JSON converter.",
            "Decorator: wraps an object to add behavior. Implements the same interface as the wrapped object. Stackable (multiple decorators).",
            "Composite: tree structure where leaves and composites share an interface. File/Directory, UI Widget trees, Org charts.",
            "Facade: simplified entry point to a complex subsystem. Hides wiring details. Example: a BookingFacade that coordinates Room, Payment, Notification.",
            "Proxy: surrogate that controls access. Types: virtual (lazy load), protection (access control), remote (network), logging/caching.",
            "Bridge: decouple abstraction from implementation. Example: Shape (abstraction) + Renderer (implementation) vary independently.",
        ],
        "canonical_problems": [
            {"name": "In-Memory File System", "slug": "in-memory-file-system", "difficulty": "hard",
             "why": "File/Directory is textbook Composite pattern; both implement FSEntry with size() and path()"},
            {"name": "Online Shopping Cart", "slug": "online-shopping-cart", "difficulty": "medium",
             "why": "Decorator for adding gift wrapping / insurance to cart items; Facade for checkout orchestration"},
            {"name": "Stack Overflow - Q&A Platform", "slug": "stack-overflow-qa-platform", "difficulty": "hard",
             "why": "Decorator for adding badges/privileges to users; Proxy for reputation-gated actions"},
        ],
        "common_mistakes": [
            "Confusing Adapter (makes incompatible interfaces work together) with Decorator (adds behavior to an existing interface)",
            "Creating a Facade that becomes a God Object -- it should delegate, not contain logic",
            "Composite without a shared interface between leaf and composite -- the whole point is uniform treatment",
            "Over-decorating: too many nested decorators make debugging painful (hard to see the original object)",
            "Using Proxy when simple method calls would suffice -- don't add indirection without a reason",
        ],
        "visual_examples": [
            {
                "description": "Composite pattern: File System tree with uniform FSEntry interface",
                "mermaid": (
                    "classDiagram\n"
                    "    class FSEntry {\n"
                    "        <<abstract>>\n"
                    "        +String name\n"
                    "        +size() int\n"
                    "        +path() String\n"
                    "    }\n"
                    "    class File {\n"
                    "        -String content\n"
                    "        +size() int\n"
                    "        +read() String\n"
                    "        +write(String)\n"
                    "    }\n"
                    "    class Directory {\n"
                    "        -Map~String,FSEntry~ children\n"
                    "        +size() int\n"
                    "        +add(FSEntry)\n"
                    "        +remove(String)\n"
                    "        +list() List~String~\n"
                    "    }\n"
                    "    FSEntry <|-- File\n"
                    "    FSEntry <|-- Directory\n"
                    "    Directory o-- FSEntry : contains"
                ),
            },
            {
                "description": "Decorator pattern: stackable enhancements on a CartItem",
                "mermaid": (
                    "classDiagram\n"
                    "    class CartItem {\n"
                    "        <<interface>>\n"
                    "        +subtotal() float\n"
                    "        +description() String\n"
                    "    }\n"
                    "    class BasicCartItem {\n"
                    "        +subtotal() float\n"
                    "        +description() String\n"
                    "    }\n"
                    "    class GiftWrapDecorator {\n"
                    "        -CartItem wrapped\n"
                    "        +subtotal() float\n"
                    "        +description() String\n"
                    "    }\n"
                    "    class InsuranceDecorator {\n"
                    "        -CartItem wrapped\n"
                    "        +subtotal() float\n"
                    "        +description() String\n"
                    "    }\n"
                    "    CartItem <|.. BasicCartItem\n"
                    "    CartItem <|.. GiftWrapDecorator\n"
                    "    CartItem <|.. InsuranceDecorator\n"
                    "    GiftWrapDecorator --> CartItem : wraps\n"
                    "    InsuranceDecorator --> CartItem : wraps"
                ),
            },
        ],
    },
    # -----------------------------------------------------------------------
    # 5. Behavioral Design Patterns
    # -----------------------------------------------------------------------
    "design-patterns-behavioral": {
        "title": "Behavioral Design Patterns",
        "topic": "Behavioral Design Patterns",
        "introduction": (
            "Behavioral patterns define how objects interact and distribute responsibility.  "
            "They shift the focus from structure to communication.  Observer (pub-sub) decouples "
            "event producers from consumers.  Strategy encapsulates interchangeable algorithms "
            "behind a common interface.  State lets an object change behavior when its internal "
            "state changes (the object appears to change its class).  Command encapsulates a "
            "request as an object, enabling undo/redo and queuing.  Template Method defines the "
            "skeleton of an algorithm with hook methods for subclasses.  Iterator provides a way "
            "to traverse a collection without exposing its internals."
        ),
        "key_ideas": [
            "Observer: when one object changes state, all dependents are notified. Used in event systems, UI updates, notification services.",
            "Strategy: define a family of algorithms, encapsulate each, and make them interchangeable. Client selects at runtime (e.g., PricingStrategy, SortStrategy).",
            "State: an object delegates behavior to its current State object. State transitions are explicit. Eliminates large if-else/switch on state.",
            "Command: encapsulate request as object with execute() and undo(). Enables: undo/redo, macro commands, command queuing, logging.",
            "Template Method: base class defines algorithm skeleton with abstract steps. Subclasses fill in the blanks without changing the overall structure.",
            "Iterator: provide sequential access to elements of a collection without exposing underlying structure. Python's __iter__/__next__ protocol.",
        ],
        "canonical_problems": [
            {"name": "Vending Machine", "slug": "vending-machine", "difficulty": "easy",
             "why": "State pattern: IdleState, HasMoneyState, DispensingState. The machine delegates all actions to its current state."},
            {"name": "Elevator System", "slug": "elevator-system", "difficulty": "hard",
             "why": "Strategy for dispatch algorithm, State for elevator modes, Observer for floor display updates, Command for button presses."},
            {"name": "Chess Game", "slug": "chess-game", "difficulty": "hard",
             "why": "Command pattern for moves (execute/undo), Strategy for different piece movement rules, Observer for check notifications."},
        ],
        "common_mistakes": [
            "Observer memory leaks: forgetting to unsubscribe observers when they are destroyed",
            "State pattern with transitions scattered across states -- use a transition table or centralized controller",
            "Strategy objects that hold state -- they should be stateless and interchangeable",
            "Command without proper undo semantics -- store enough state to reverse the action",
            "Template Method with too many hooks -- signals the algorithm should be decomposed differently",
        ],
        "visual_examples": [
            {
                "description": "State pattern: Vending Machine state transitions",
                "mermaid": (
                    "stateDiagram-v2\n"
                    "    [*] --> Idle\n"
                    "    Idle --> HasMoney : insertCoin()\n"
                    "    HasMoney --> HasMoney : insertCoin()\n"
                    "    HasMoney --> Dispensing : selectProduct() [sufficient funds]\n"
                    "    HasMoney --> Idle : cancel() [return coins]\n"
                    "    Dispensing --> Idle : dispense() [success]\n"
                    "    Dispensing --> HasMoney : dispense() [out of stock]"
                ),
            },
            {
                "description": "Observer pattern: BookingService notifies multiple listeners",
                "mermaid": (
                    "classDiagram\n"
                    "    class BookingService {\n"
                    "        -List~BookingObserver~ observers\n"
                    "        +subscribe(BookingObserver)\n"
                    "        +unsubscribe(BookingObserver)\n"
                    "        +confirmBooking()\n"
                    "    }\n"
                    "    class BookingObserver {\n"
                    "        <<interface>>\n"
                    "        +onBookingConfirmed(Booking)\n"
                    "    }\n"
                    "    class EmailNotifier {\n"
                    "        +onBookingConfirmed(Booking)\n"
                    "    }\n"
                    "    class InventoryUpdater {\n"
                    "        +onBookingConfirmed(Booking)\n"
                    "    }\n"
                    "    class AnalyticsTracker {\n"
                    "        +onBookingConfirmed(Booking)\n"
                    "    }\n"
                    "    BookingService --> BookingObserver\n"
                    "    BookingObserver <|.. EmailNotifier\n"
                    "    BookingObserver <|.. InventoryUpdater\n"
                    "    BookingObserver <|.. AnalyticsTracker"
                ),
            },
        ],
    },
    # -----------------------------------------------------------------------
    # 6. UML Class Diagrams
    # -----------------------------------------------------------------------
    "uml-class-diagrams": {
        "title": "UML Class Diagrams",
        "topic": "UML Class Diagrams",
        "introduction": (
            "UML class diagrams are the standard visual language for LLD.  In an interview, "
            "you sketch a class diagram before writing code -- it communicates your design "
            "quickly and unambiguously.  You need to know: classes (name, attributes, methods), "
            "visibility modifiers (+public, -private, #protected), relationships (association, "
            "aggregation, composition, inheritance, realization), multiplicity (1, 0..*, 1..*), "
            "and stereotypes (<<interface>>, <<abstract>>, <<enum>>).  A good class diagram "
            "shows the entities, their responsibilities, and how they collaborate."
        ),
        "key_ideas": [
            "Class box: three compartments -- name (top), attributes (middle), methods (bottom). Use +/-/# for visibility.",
            "Association (solid line): general relationship between classes. Add role names and multiplicity (1, 0..1, 0..*, 1..*).",
            "Aggregation (empty diamond): weak has-a. The part can exist independently (Department has Professors; professors exist without the department).",
            "Composition (filled diamond): strong has-a. The part cannot exist without the whole (Room belongs to Hotel; delete hotel, delete rooms).",
            "Inheritance/Generalization (empty triangle arrow): is-a relationship. Subclass extends superclass.",
            "Realization (dashed triangle arrow): class implements an interface. E.g., HourlyPricing implements PricingStrategy.",
            "Dependency (dashed arrow): one class uses another temporarily (e.g., method parameter). Weakest relationship.",
        ],
        "canonical_problems": [
            {"name": "Parking Lot System", "slug": "parking-lot-system", "difficulty": "medium",
             "why": "Rich class diagram with composition (ParkingLot --* ParkingFloor --* ParkingSpot), inheritance (Vehicle types), and realization (PricingStrategy)"},
            {"name": "In-Memory File System", "slug": "in-memory-file-system", "difficulty": "hard",
             "why": "Composite pattern visualized: Directory --o FSEntry (aggregation), File and Directory both realize FSEntry"},
            {"name": "Splitwise - Expense Sharing", "slug": "splitwise-expense-sharing", "difficulty": "medium",
             "why": "Association with multiplicity: User 1..* -- * Group, Expense * -- 1 User (paidBy), Split strategy realization"},
        ],
        "common_mistakes": [
            "Confusing aggregation (open diamond) with composition (filled diamond) -- composition means the part dies with the whole",
            "Forgetting multiplicity labels -- they communicate critical cardinality constraints",
            "Drawing inheritance arrows in the wrong direction (arrow points FROM subclass TO superclass)",
            "Putting implementation details (private helper methods) in the diagram -- focus on public interface",
            "Missing interfaces and abstract classes -- these are the most important design decisions to show",
        ],
        "visual_examples": [
            {
                "description": "Complete class diagram for a simplified Parking Lot showing all relationship types",
                "mermaid": (
                    "classDiagram\n"
                    "    class ParkingLot {\n"
                    "        -String name\n"
                    "        -List~ParkingFloor~ floors\n"
                    "        +park(Vehicle) Ticket\n"
                    "        +unpark(Ticket) float\n"
                    "    }\n"
                    "    class ParkingFloor {\n"
                    "        -int floorNumber\n"
                    "        -List~ParkingSpot~ spots\n"
                    "        +getAvailableSpots(VehicleType) List\n"
                    "    }\n"
                    "    class ParkingSpot {\n"
                    "        -String spotId\n"
                    "        -VehicleType spotType\n"
                    "        -Vehicle vehicle\n"
                    "        +isAvailable() bool\n"
                    "        +assignVehicle(Vehicle)\n"
                    "    }\n"
                    "    class Vehicle {\n"
                    "        <<abstract>>\n"
                    "        -String licensePlate\n"
                    "    }\n"
                    "    class Car\n"
                    "    class Truck\n"
                    "    class PricingStrategy {\n"
                    "        <<interface>>\n"
                    "        +calculateFee() float\n"
                    "    }\n"
                    "    class Ticket {\n"
                    "        -String ticketId\n"
                    "        -DateTime entryTime\n"
                    "    }\n"
                    "    ParkingLot *-- ParkingFloor : 1..*\n"
                    "    ParkingFloor *-- ParkingSpot : 1..*\n"
                    "    ParkingSpot --> Vehicle : 0..1\n"
                    "    Vehicle <|-- Car\n"
                    "    Vehicle <|-- Truck\n"
                    "    ParkingLot --> PricingStrategy\n"
                    "    ParkingLot ..> Ticket : creates"
                ),
            },
        ],
    },
    # -----------------------------------------------------------------------
    # 7. LLD Problem-Solving Framework
    # -----------------------------------------------------------------------
    "lld-framework": {
        "title": "LLD Problem-Solving Framework",
        "topic": "LLD Problem-Solving Framework",
        "introduction": (
            "LLD interviews follow a predictable structure.  If you have a framework, "
            "you can tackle any problem systematically instead of fumbling.  The flow is: "
            "(1) Clarify requirements -- ask about scope, constraints, and edge cases.  "
            "(2) Identify core entities -- the nouns in the problem statement become classes.  "
            "(3) Define relationships -- who owns whom, what multiplicities, composition vs aggregation.  "
            "(4) Assign responsibilities -- each class should have clear, focused methods (SRP).  "
            "(5) Identify patterns -- Strategy for varying behavior, State for state machines, "
            "Observer for events, Factory for object creation.  (6) Define APIs -- public methods "
            "that clients will call.  (7) Write code -- implement the core classes with clean OOP.  "
            "Budget: ~5 min requirements, ~5 min entities + relationships (class diagram), "
            "~25 min code, ~5 min edge cases."
        ),
        "key_ideas": [
            "Step 1 - Requirements: List functional requirements (what the system does) and non-functional (how: concurrency, scalability). Ask clarifying questions.",
            "Step 2 - Entities: Identify the core objects from the problem. Nouns in the requirements become classes. Group related attributes together.",
            "Step 3 - Relationships: Draw associations. Determine multiplicity (1:1, 1:N, N:M). Decide composition vs aggregation. Identify inheritance hierarchies.",
            "Step 4 - Responsibilities: Assign methods to classes following SRP. If a method doesn't belong to a class, create a service/manager class.",
            "Step 5 - Patterns: Look for Strategy (variable algorithm), State (finite state machine), Observer (events), Factory (object creation), Builder (complex construction).",
            "Step 6 - API Design: Define the public interface. Input types, return types, exceptions. This is the contract your interviewer evaluates.",
            "Step 7 - Implementation: Write clean code. Use enums for fixed categories, abstract classes for hierarchies, interfaces for pluggable behavior.",
        ],
        "canonical_problems": [
            {"name": "Parking Lot System", "slug": "parking-lot-system", "difficulty": "medium",
             "why": "The canonical LLD warm-up. Covers all 7 steps cleanly: clear entities, Strategy pattern, straightforward API."},
            {"name": "Movie Ticket Booking System", "slug": "movie-ticket-booking-system", "difficulty": "hard",
             "why": "Tests concurrency thinking (seat locking), state management (hold -> booked), and multi-entity relationships."},
            {"name": "Elevator System", "slug": "elevator-system", "difficulty": "hard",
             "why": "Tests algorithmic thinking within an OOP design. Scheduling strategy, state machine, and real-time dispatch."},
        ],
        "common_mistakes": [
            "Jumping to code without clarifying requirements -- you'll redesign midway",
            "Too many entities: not every noun deserves a class. A 'Name' is a string, not a class.",
            "Too few entities: cramming everything into one God class with 20 methods",
            "Ignoring concurrency: booking systems, elevators, and rate limiters need thread safety",
            "Ignoring edge cases: what happens when the parking lot is full? When an elevator is in maintenance? When a product is out of stock?",
            "Not drawing a class diagram first -- visual design catches relationship errors early",
        ],
        "visual_examples": [
            {
                "description": "LLD interview framework: the 7-step process",
                "mermaid": (
                    "flowchart LR\n"
                    "    A[1. Requirements] --> B[2. Entities]\n"
                    "    B --> C[3. Relationships]\n"
                    "    C --> D[4. Responsibilities]\n"
                    "    D --> E[5. Patterns]\n"
                    "    E --> F[6. API Design]\n"
                    "    F --> G[7. Implementation]\n"
                    "    G -->|Edge cases| A"
                ),
            },
            {
                "description": "Entity identification from requirements: Parking Lot example",
                "mermaid": (
                    "mindmap\n"
                    "  root((Parking Lot))\n"
                    "    Vehicles\n"
                    "      Car\n"
                    "      Motorcycle\n"
                    "      Truck\n"
                    "    Infrastructure\n"
                    "      ParkingFloor\n"
                    "      ParkingSpot\n"
                    "      EntranceGate\n"
                    "      ExitGate\n"
                    "    Operations\n"
                    "      Ticket\n"
                    "      PricingStrategy\n"
                    "      DisplayBoard"
                ),
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Seed script
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed LLD problems and teaching plans into MongoDB")
    parser.add_argument("--uri", type=str, default=None, help="MongoDB URI override")
    args = parser.parse_args()

    # Load env
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)
    sys.path.insert(0, os.path.join(root, "backend"))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, "backend", ".env"), override=False)
    except ImportError:
        pass

    uri = args.uri or os.environ.get("MONGODB_URI", "")
    if not uri:
        print("ERROR: MONGODB_URI not set. Set it in backend/.env or pass --uri.")
        sys.exit(1)

    import certifi
    from pymongo import MongoClient

    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client["tutor_v2"]

    # ------------------------------------------------------------------
    # 1. Seed LLD Problems into sd_problems
    # ------------------------------------------------------------------
    col_problems = db["sd_problems"]
    print("\n=== Seeding LLD Problems into capacity.sd_problems ===")

    for p in LLD_PROBLEMS:
        result = col_problems.update_one(
            {"slug": p["slug"]},
            {"$set": p},
            upsert=True,
        )
        action = "updated" if result.matched_count > 0 else "inserted"
        print(f"  [{action}] {p['num']:>2}. {p['name']} ({p['difficulty']})")

    # Ensure indexes exist
    col_problems.create_index("slug", unique=True)
    col_problems.create_index("type")
    print(f"\n  Total LLD problems seeded: {len(LLD_PROBLEMS)}")
    print("  Indexes ensured: slug (unique), type")

    # ------------------------------------------------------------------
    # 2. Seed LLD Teaching Plans into teaching_plans
    # ------------------------------------------------------------------
    col_plans = db["teaching_plans"]
    print("\n=== Seeding LLD Teaching Plans into capacity.teaching_plans ===")

    for slug, plan in LLD_TEACHING_PLANS.items():
        doc = {
            "slug": slug,
            "type": "lld",
            **plan,
        }
        result = col_plans.update_one(
            {"slug": slug},
            {"$set": doc},
            upsert=True,
        )
        action = "updated" if result.matched_count > 0 else "inserted"
        print(f"  [{action}] {slug}")

    # Ensure indexes exist
    col_plans.create_index("slug", unique=True)
    col_plans.create_index("type")
    print(f"\n  Total LLD teaching plans seeded: {len(LLD_TEACHING_PLANS)}")
    print("  Indexes ensured: slug (unique), type")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total_sd = col_problems.count_documents({"type": "lld"})
    total_plans = col_plans.count_documents({"type": "lld"})
    print(f"\n=== Summary ===")
    print(f"  LLD problems  in sd_problems:    {total_sd}")
    print(f"  LLD plans     in teaching_plans:  {total_plans}")
    print(f"  (HLD problems in sd_problems:     {col_problems.count_documents({'type': {'$ne': 'lld'}})})")
    print(f"  (DSA plans    in teaching_plans:   {col_plans.count_documents({'type': 'dsa'})})")
    print(f"  (SD  plans    in teaching_plans:   {col_plans.count_documents({'type': 'sd'})})")
    print("\nDone!")

    client.close()


if __name__ == "__main__":
    main()
