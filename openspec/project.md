# Project Context

## Purpose
Model Auction is a platform for auctioning AI/ML models. The system enables:
- Model owners to list and auction their trained models
- Buyers to bid on and purchase models
- Auction management with bidding, payment processing, and model transfer

**Goals:**
- Provide a secure marketplace for model transactions
- Support various auction types (e.g., English auction, sealed bid)
- Ensure model authenticity and transfer integrity
- Enable fair and transparent bidding processes

## Tech Stack
- **Backend**: [To be determined - e.g., Node.js/TypeScript, Python/FastAPI, Go]
- **Frontend**: [To be determined - e.g., React/TypeScript, Next.js]
- **Database**: [To be determined - e.g., PostgreSQL, MongoDB]
- **Authentication**: [To be determined - e.g., JWT, OAuth2]
- **Payment Processing**: [To be determined - e.g., Stripe, PayPal]
- **File Storage**: [To be determined - e.g., AWS S3, Cloud Storage]
- **Container/Deployment**: [To be determined - e.g., Docker, Kubernetes]

## Project Conventions

### Code Style
- Use consistent formatting (Prettier/Black/Go fmt based on language)
- Follow language-specific style guides (e.g., Google Style Guide, Airbnb)
- Use meaningful variable and function names
- Prefer explicit over implicit
- Keep functions small and focused (single responsibility)
- Maximum function length: ~50 lines (exceptions for data structures)

### Architecture Patterns
- **Layered Architecture**: Separate concerns (presentation, business logic, data access)
- **RESTful API**: Use standard HTTP methods and status codes
- **Domain-Driven Design**: Organize code around business domains (auctions, models, users)
- **Repository Pattern**: Abstract data access layer
- **Dependency Injection**: Enable testability and flexibility

### Testing Strategy
- **Unit Tests**: Test individual functions/components in isolation
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test critical user flows (auction creation, bidding, purchase)
- **Test Coverage**: Aim for >80% coverage on business logic
- **Test-Driven Development**: Write tests before implementation when feasible
- Use descriptive test names: `test_should_reject_bid_when_auction_closed`

### Git Workflow
- **Branching**: Feature branches from `main` (e.g., `feature/add-bidding`, `fix/payment-bug`)
- **Commits**: 
  - Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
  - Write clear, descriptive commit messages
  - Keep commits atomic (one logical change per commit)
- **Pull Requests**: 
  - Require code review before merging
  - All tests must pass
  - Update documentation as needed
- **Main Branch**: Always deployable, protected

## Domain Context

### Core Entities
- **Model**: A trained AI/ML model with metadata (architecture, training data, performance metrics)
- **Auction**: A time-bound event where models are sold to the highest bidder
- **Bid**: An offer to purchase a model at a specific price
- **User**: Can be a seller (model owner) or buyer (bidder)

### Auction Types
- **English Auction**: Open ascending price, highest bidder wins
- **Sealed Bid**: Bidders submit private bids, highest wins
- **Dutch Auction**: Descending price until someone accepts

### Key Business Rules
- Bids must be higher than current highest bid (or minimum bid)
- Auctions have start/end times
- Models must be verified before listing
- Payment must be processed before model transfer
- Sellers receive payment minus platform fee

## Important Constraints
- **Security**: 
  - All model files must be encrypted in transit and at rest
  - Payment information must comply with PCI DSS
  - User authentication must be secure (2FA recommended)
- **Performance**: 
  - Auction updates must be real-time (<1s latency)
  - Support concurrent bidding without race conditions
- **Legal**: 
  - Model licensing terms must be clearly defined
  - Compliance with data protection regulations (GDPR, CCPA)
  - Intellectual property rights must be respected
- **Scalability**: 
  - System must handle 1000+ concurrent auctions
  - Support models up to 10GB in size

## External Dependencies
- **Payment Gateway**: [e.g., Stripe, PayPal] - Process payments securely
- **Cloud Storage**: [e.g., AWS S3, Google Cloud Storage] - Store model files
- **Email Service**: [e.g., SendGrid, AWS SES] - Send notifications
- **Identity Provider**: [e.g., Auth0, AWS Cognito] - User authentication (optional)
- **Monitoring**: [e.g., Datadog, New Relic] - Application monitoring and logging
