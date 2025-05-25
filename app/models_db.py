import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, Enum as SQLAlchemyEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID # For type, works with SQLite too
from app.database import Base
# Import Pydantic enums for use in SQLAlchemy models
from app.models.api_key import ApiMode 
from app.models.strategy import CoverReferencePrice, OrderType

class ApiKeyDB(Base):
    __tablename__ = "api_keys"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alias = Column(String, index=True, nullable=False)
    api_key = Column(String, nullable=False)
    secret_key = Column(String, nullable=False) # Should be encrypted in a real app
    mode = Column(SQLAlchemyEnum(ApiMode), nullable=False)
    # connection_status is omitted from DB

class StrategyConfigDB(Base):
    __tablename__ = "strategy_configs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(PG_UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    
    strategy_name = Column(String, index=True, nullable=False)
    trading_pair = Column(String, nullable=False)
    initial_order_amount_usdt = Column(Float, nullable=False)
    
    buy_trigger_fall_percentage = Column(Float, default=0.0) # Ensure default is float
    buy_confirm_callback_percentage = Column(Float, default=0.0) # Ensure default is float
    sell_trigger_rise_percentage = Column(Float, nullable=False)
    sell_callback_percentage = Column(Float, nullable=False)
    
    max_cover_count = Column(Integer, nullable=False)
    cover_multiplier = Column(Float, default=1.0)
    cover_trigger_fall_percentage = Column(Float, nullable=False)
    cover_confirm_callback_percentage = Column(Float, nullable=False)
    cover_reference_price = Column(SQLAlchemyEnum(CoverReferencePrice), nullable=False)
    
    order_type = Column(SQLAlchemyEnum(OrderType), nullable=False)
    cyclic_execution = Column(Boolean, default=True)
    cover_orders_participate_in_profit_taking = Column(Boolean, default=False)
    enable_order_timeout = Column(Boolean, default=False)
    order_timeout_seconds = Column(Integer, default=60)

    # Relationship
    api_key = relationship("ApiKeyDB")
