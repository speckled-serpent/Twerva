# Twerva Code Style Guide

*Version: 1.1.0*  
*Applies to: Python, TypeScript, TSX, and all codebase languages*

This guide defines the readable code standards for Twerva. Adapted from Spotmu’s style guide so both projects stay disciplined the same way. These rules prioritize **type clarity** and **semantic explicitness** over brevity.

---

## 1. Type Hints on ALL Variables

Every variable declaration must include an explicit type hint.

**Python:**
```python
# Correct
user_email: str = "alice@example.com"
story_count: int = 0
matching_stories: list[GlobalStory] = []
user_lookup: dict[str, User] = {}

# Incorrect
user_email = "alice@example.com"  # Missing type hint
story_count = 0  # Missing type hint
```

**TypeScript:**
```typescript
// Correct
const userEmail: string = "alice@example.com";
const storyCount: number = 0;
const matchingStories: GlobalStory[] = [];
const userLookup: Map<string, User> = new Map();

// Incorrect
const userEmail = "alice@example.com";  // Missing type hint (when not contextually inferred)
let storyCount = 0;  // Missing type hint
```

**Rationale:** The type of a variable often communicates more than its name. Static typing eliminates ambiguity and enables IDE assistance.

---

## 2. Logic Spacing Between Semantic Groups

Insert blank lines between logical paragraphs. Code is read like prose—group related operations, separate distinct phases.

```python
# Correct
async def fetch_user_profile_and_interests(
    user_identifier: str,
    our_users_database: AsyncSession
) -> tuple[OurUsers, list[UserInterest]]:

    """Fetch user profile and interests."""
    user_profile: OurUsers = await fetch_user_profile(user_identifier)
    interest_embeddings: list[Embedding] = await fetch_interest_embeddings(user_identifier)

    affinity_scores: dict[str, float] = calculate_affinity_scores(user_profile, interest_embeddings)
    ranked_interests: list[RankedInterest] = sort_by_composite_score(affinity_scores)

    return user_profile, ranked_interests

# Incorrect
async def generate_briefing(user_id, db):
    user_profile = await fetch_profile(user_id)
    interest_embeddings = await fetch_embeddings(user_id)
    affinity_scores = calculate_scores(user_profile, interest_embeddings)
    ranked_interests = sort_by_score(affinity_scores)
    return assemble_feed(ranked_interests)
```

**Rationale:** Visual separation mirrors conceptual separation. Dense code requires more cognitive effort to parse.

---

## 2A. Explicit Function Signature and Body Formatting

These rules define specific structural requirements for function declarations and control flow blocks to maximize readability.

### 2A.1 Function Parameters Stay on Declaration Line

Parameters remain on the same line as the function declaration **unless** there are 6 or more parameters.

**Python:** The return type annotation goes on its own line.

```python
# Correct (fewer than 6 parameters)
async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:

# Correct (6+ parameters—stack vertically)
async def fetch_stories_with_complex_filtering(
    user_identifier: str,
    interest_identifiers: list[str],
    our_stories_database: Session,
    minimum_actionability_score: int = 5,
    maximum_story_age_hours: int = 48,
    include_archived: bool = False
) -> list[OurStories]:
```

**TypeScript/TSX:** Return type stays on the same line as the closing parenthesis.

```typescript
// Correct (fewer than 6 parameters)
async function fetchUserByEmailAddress(
  email: string,
  database: Database
): Promise<User> {

// Correct (6+ parameters—stack vertically)
async function fetchStoriesWithComplexFiltering(
  userId: string,
  interestIds: string[],
  database: Database,
  minScore: number = 5,
  maxAge: number = 48,
  includeArchived: boolean = false
): Promise<Story[]> {
```

### 2A.2 Return Type Placement

**Python:** Return type annotation must be on its own line, indented to align with the opening parenthesis.

```python
# Correct
async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:

# Incorrect (return type crammed on same line)
async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]],) -> Response:
```

**TypeScript/TSX:** Return type stays on the same line as the closing parenthesis.

```typescript
// Correct
async function fetchUserByEmailAddress(
  email: string,
  database: Database
): Promise<User> {

// Incorrect (return type on separate line)
async function fetchUserByEmailAddress(
  email: string,
  database: Database
)
: Promise<User> {
```

### 2A.3 Blank Line After Function Signature

A blank line must separate the function signature (including return type) from the first line of function body.

**Python:**
```python
# Correct
async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:

    start_time: float = time.perf_counter()
    response: Response

# Incorrect
async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start_time: float = time.perf_counter()
    response: Response
```

**TypeScript/TSX:**
```typescript
// Correct
async function fetchUserByEmailAddress(
  email: string,
  database: Database
): Promise<User> {

  const startTime: number = performance.now();
  const response: Response;

// Incorrect
async function fetchUserByEmailAddress(
  email: string,
  database: Database
): Promise<User> {
  const startTime: number = performance.now();
  const response: Response;
```

### 2A.4 Logic Blocks Separated by Blank Lines

Control flow blocks (`if`/`else`, `try`/`except`/`finally`, `for`, `while`, `with`) must be separated from surrounding code by a blank line on both sides.

```python
# Correct
    start_time: float = time.perf_counter()
    response: Response

    try:
        response = await call_next(request)
    finally:
        duration_milliseconds: float = (time.perf_counter() - start_time) * 1000

    latency_store.record(endpoint_path, duration_milliseconds)

# Incorrect
    start_time: float = time.perf_counter()
    response: Response
    try:
        response = await call_next(request)
    finally:
        duration_milliseconds: float = (time.perf_counter() - start_time) * 1000
    latency_store.record(endpoint_path, duration_milliseconds)
```

### 2A.5 Return Statements Separated by Blank Line

Return statements must be preceded by a blank line to visually distinguish the output point.

```python
# Correct
            else:
                # Unmatched route (404, scanner traffic, etc.)
                endpoint_path = "<unmatched>"
            latency_store.record(endpoint_path, duration_milliseconds)

        return response

# Incorrect
            else:
                # Unmatched route (404, scanner traffic, etc.)
                endpoint_path = "<unmatched>"
            latency_store.record(endpoint_path, duration_milliseconds)
        return response
```

### Complete Example

Applying all formatting rules together:

```python
# Before (non-compliant)
async def dispatch(
    self,
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start_time: float = time.perf_counter()
    response: Response
    try:
        response = await call_next(request)
    finally:
        duration_milliseconds: float = (time.perf_counter() - start_time) * 1000
        route: Any | None = request.scope.get("route")
        endpoint_path: str
        if route is not None and hasattr(route, "path"):
            endpoint_path = route.path
        else:
            endpoint_path = "<unmatched>"
        latency_store.record(endpoint_path, duration_milliseconds)
    return response

# After (compliant)
async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:

    start_time: float = time.perf_counter()
    response: Response

    try:
        response = await call_next(request)
    finally:
        duration_milliseconds: float = (time.perf_counter() - start_time) * 1000
        route: Any | None = request.scope.get("route")
        endpoint_path: str

        if route is not None and hasattr(route, "path"):
            endpoint_path = route.path
        else:
            endpoint_path = "<unmatched>"
        latency_store.record(endpoint_path, duration_milliseconds)

    return response
```

**Rationale:** These structural rules make the function's contract (signature) visually distinct from its implementation (body), and make control flow boundaries immediately apparent. The return type stands out as part of the function's interface, not its logic.

---

## 3. Break Up Chained Operations into Named Variables

Never nest method chains. Decompose into named intermediate variables that reveal each transformation step.

**NOT:**
```python
source = our_database_session.query(OurSources).filter(OurSources.source_hash_id == source_hash_id).first()
```

**Correct:**
```python
full_query: Query = our_database_session.query(OurSources)
matching_identifier: ColumnElement[bool] = OurSources.source_hash_id == source_hash_id
filtered_query: Query = full_query.filter(matching_identifier)
found_source: OurSources | None = filtered_query.first()
```

**Another Example:**

**NOT:**
```python
return [
    transform(story)
    for story in (
        our_stories_database.query(OurStories)
        .filter(OurStories.created_at > cutoff_date)
        .order_by(OurStories.public_value_score.desc())
        .limit(100)
        .all()
    )
    if story.actionability_score > threshold
]
```

**Correct:**
```python
async def fetch_and_transform_stories(
    cutoff_date: datetime,
    threshold: int,
    our_stories_database: AsyncSession
) -> list[TransformedStory]:
    """Fetch and transform stories."""
    recent_stories_query: Query = our_stories_database.query(OurStories)
    recent_filter: ColumnElement[bool] = OurStories.created_at > cutoff_date
    ordered_query: Query = recent_stories_query.filter(recent_filter).order_by(
        OurStories.public_value_score.desc()
    )
    top_stories: list[OurStories] = ordered_query.limit(100).all()

    high_actionability_stories: list[OurStories] = [
        story for story in top_stories
        if story.actionability_score > threshold
    ]

    return [transform_story(story) for story in high_actionability_stories]
```

**Rationale:** Named intermediates are self-documenting. They provide natural breakpoints for debugging and make each transformation explicit.

---

## 4. Variable Names: Full Words, Not Abbreviations

Use complete words. Clarity > brevity.

| Avoid | Use Instead |
|-------|-------------|
| `src` | `source` |
| `usr` | `user` |
| `auth` | `authentication` |
| `resp` | `response` |
| `req` | `request` |
| `db` | `database` (or `our_stories_database` per Rule 6) |
| `err` | `error` |
| `idx` | `index` |
| `msg` | `message` |
| `cfg` | `configuration` |
| `ctx` | `context` |
| `handler` | `request_handler` or `error_handler` |
| `data` | `story_data` or `user_profile_data` |

**Correct:**
```python
user_email_address: str = user.email_address
error_message: str = format_error_message(error)
```

**Rationale:** Abbreviations impose decoding overhead. Full words are immediately readable by all team members, including future you.

---

## 5. Function Names Should Be as Specific as Possible

Function names must describe exactly what they retrieve or compute, including context.

| Avoid | Use Instead |
|-------|-------------|
| `_source_or_404` | `_source_page_or_404` |
| `get_user` | `get_user_by_email_address` |
| `validate` | `validate_authentication_token` |
| `process` | `process_news_article_content` |
| `calculate` | `calculate_public_value_rank` |
| `filter` | `filter_stories_by_time_horizon` |
| `check` | `check_source_authentication_status` |

**Correct:**
```python
async def fetch_user_by_email_address(
    email_address: str,
    our_users_database: AsyncSession
) -> OurUsers:
    """Fetch a user by email address."""
    ...
```

**Rationale:** Specific names reduce the need to read function bodies. They prevent naming collisions and clarify scope.

---

## 6. Database References: Always "Our" + Plural

Database tables, ORM model classes that initialize databases, and variables referencing database sessions must:
- Start with `Our`
- Use plural form

| Avoid | Use Instead |
|-------|-------------|
| `Story(Base)` | `OurStories(Base)` |
| `User(Base)` | `OurUsers(Base)` |
| `db` | `our_stories_database` |
| `session` | `our_database_session` |
| `engine` | `our_database_engine` |
| `Interest(Base)` | `OurInterests(Base)` |
| `Source(Base)` | `OurSources(Base)` |

**Python:**
```python
class OurStories(Base):
    """Database table storing synthesized story records."""
    __tablename__ = "global_stories"
    ...

async def fetch_story(
    story_hash_id: str,
    our_stories_database: AsyncSession
) -> OurStories | None:
    ...
```

**TypeScript/TSX:**
```typescript
// Interface naming follows same convention
interface OurStories {
  id: string;
  title: string;
  body: string;
  createdAt: Date;
}

// Database service naming
const ourStoriesDatabase: DatabaseService = new DatabaseService();

// Repository pattern
class StoriesRepository {
  async findByHashId(hashId: string): Promise<OurStories | null> {
    return this.database.stories.find({ hash_id: hashId });
  }
}

// Usage
async function fetchStory(
  storyHashId: string,
  ourStoriesDatabase: DatabaseService
): Promise<OurStories | null> {
  return ourStoriesDatabase.findByHashId(storyHashId);
}
```

**Rationale:** The `Our` prefix immediately signals "this is a database table/class," distinguishing it from a single instance. Plural form reinforces that this represents a collection/table, not an individual record.

---

## 7. Collections: Plural Names. Single Objects: Singular Names

Never use plural names for single objects or singular names for collections.

| Context | Incorrect | Correct |
|---------|-----------|---------|
| Single story | `stories = fetch_story(id)` | `story = fetch_story(id)` |
| List of stories | `story_list = fetch_all()` | `stories = fetch_all()` |
| Dictionary mapping | `story_dict = {...}` | `stories_by_id = {...}` |
| Single user | `users = get_user(email)` | `user = get_user(email)` |
| Array of scores | `score = [1, 2, 3]` | `scores = [1, 2, 3]` |

**Correct:**
```python
story: OurStories = await fetch_story_by_hash_id(story_hash_id)
stories: list[OurStories] = await fetch_stories_for_interest(interest_identifier)
affinity_scores_by_story_id: dict[str, float] = compute_affinity_scores(stories)
```

**Rationale:** Grammatical agreement between name and cardinality eliminates mental translation overhead.

---

## 8. Single Responsibility: One Function, One Purpose

Every function must do exactly one thing. If a function contains sequential stages, decompose into private helper functions.

**Correct:**
```python
async def generate_personalized_briefing(
    user_identifier: str,
    our_stories_database: AsyncSession
) -> BriefingDocument:
    """Generate a personalized briefing document for a user."""
    user_interests: list[UserInterest] = await _fetch_user_interests(
        user_identifier, our_stories_database
    )
    candidate_stories: list[OurStories] = await _fetch_candidate_stories(
        user_interests, our_stories_database
    )
    scored_stories: list[ScoredStory] = _apply_relevance_scoring(
        candidate_stories, user_interests
    )
    ranked_stories: list[OurStories] = _sort_by_composite_score(scored_stories)
    return _assemble_briefing_document(ranked_stories, user_interests)


async def _fetch_user_interests(
    user_identifier: str,
    our_stories_database: AsyncSession
) -> list[UserInterest]:
    """Retrieve all active interests for a user."""
    ...


async def _fetch_candidate_stories(
    user_interests: list[UserInterest],
    our_stories_database: AsyncSession
) -> list[OurStories]:
    """Fetch candidate stories matching user's interest subscriptions."""
    ...


def _apply_relevance_scoring(
    candidate_stories: list[OurStories],
    user_interests: list[UserInterest]
) -> list[ScoredStory]:
    """Apply relevance scoring to candidate stories."""
    ...


def _sort_by_composite_score(
    scored_stories: list[ScoredStory]
) -> list[OurStories]:
    """Sort stories by composite relevance score."""
    ...


def _assemble_briefing_document(
    ranked_stories: list[OurStories],
    user_interests: list[UserInterest]
) -> BriefingDocument:
    """Assemble final briefing document from ranked stories."""
    ...
```

**Incorrect:**
```python
async def generate_briefing(user_id: str, db: AsyncSession) -> BriefingDocument:
    # Fetch user interests
    interests = await db.query(UserInterest).filter(...).all()
    
    # Fetch candidate stories
    stories = []
    for interest in interests:
        matches = await db.query(...).filter(...).all()
        stories.extend(matches)
    
    # Score stories
    scored = []
    for story in stories:
        score = calculate_score(story)
        scored.append((story, score))
    
    # Sort
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Assemble
    return BriefingDocument(stories=[s[0] for s in scored])
```

**Rationale:** Single-purpose functions are testable, reusable, and self-documenting. Private helpers enable reading from abstraction to detail (top-to-bottom).

---

## 9. Script Organization: Top-to-Bottom Reading Order

Structure files so they read from high abstraction to low detail. Public functions appear before their private helpers.

### Required Order:

1. **Imports / Namespaces** — External dependencies first, then internal
2. **Constants** — Module-level constants and configuration
3. **Variables** — Module-level state (rare, prefer dependency injection)
4. **Properties** — Getters, setters, computed properties
5. **Public Function A** — High-level entry point
6. **Private Functions for A** — Helpers used exclusively by Function A
7. **Public Function B** — Next high-level entry point
8. **Private Functions for B** — Helpers used exclusively by Function B
9. **Shared Private Functions** — Helpers used by multiple public functions (place below the lowest public function that uses them)

### Example Structure:

```python
# 1. IMPORTS
from sqlalchemy.orm import Session
from typing import Optional

from our_project.models import OurStories, OurUsers
from our_project.services import calculate_affinity_score


# 2. CONSTANTS
DEFAULT_STORY_LIMIT: int = 25
MAX_STORY_AGE_HOURS: int = 48


# 3. MODULE VARIABLES (rare)
_cache_initialized: bool = False


# 4. PROPERTIES
@property
def _cache_ready() -> bool:
    global _cache_initialized
    return _cache_initialized


# 5. PUBLIC FUNCTION A
async def fetch_personalized_feed(
    user_email_address: str,
    our_stories_database: Session
) -> FeedDocument:
    """Generate a personalized feed for a user."""
    user: OurUsers = await _fetch_user_by_email_address_or_raise(
        user_email_address, our_stories_database
    )
    interests: list[UserInterest] = await _fetch_active_interests(
        user.user_hash_id, our_stories_database
    )
    stories: list[OurStories] = await _fetch_stories_for_interests(
        interests, our_stories_database
    )
    return _assemble_feed_document(stories, interests)


# 6. PRIVATE FUNCTIONS FOR A
async def _fetch_user_by_email_address_or_raise(
    email_address: str,
    our_stories_database: Session
) -> OurUsers:
    """Fetch user by email or raise NotFoundError."""
    ...


async def _fetch_active_interests(
    user_hash_id: str,
    our_stories_database: Session
) -> list[UserInterest]:
    """Fetch all active interests for a user."""
    ...


async def _fetch_stories_for_interests(
    interests: list[UserInterest],
    our_stories_database: Session
) -> list[OurStories]:
    """Fetch candidate stories for a list of interests."""
    ...


def _assemble_feed_document(
    stories: list[OurStories],
    interests: list[UserInterest]
) -> FeedDocument:
    """Assemble stories into a feed document."""
    ...


# 7. PUBLIC FUNCTION B
async def refresh_interest_matches(
    interest_id: str,
    our_stories_database: Session
) -> int:
    """Refresh all story matches for an interest. Returns match count."""
    interest: Interest = await _fetch_interest_or_raise(
        interest_id, our_stories_database
    )
    candidate_stories: list[OurStories] = await _fetch_recent_stories(
        our_stories_database
    )
    matches: list[StoryInterestMatch] = _compute_matches(
        interest, candidate_stories
    )
    await _persist_matches(matches, our_stories_database)
    return len(matches)


# 8. PRIVATE FUNCTIONS FOR B
async def _fetch_interest_or_raise(
    interest_id: str,
    our_stories_database: Session
) -> Interest:
    """Fetch interest by ID or raise NotFoundError."""
    ...


async def _fetch_recent_stories(
    our_stories_database: Session
) -> list[OurStories]:
    """Fetch stories from the last N hours."""
    ...


def _compute_matches(
    interest: Interest,
    stories: list[OurStories]
) -> list[StoryInterestMatch]:
    """Compute affinity matches between interest and stories."""
    ...


async def _persist_matches(
    matches: list[StoryInterestMatch],
    our_stories_database: Session
) -> None:
    """Persist match records to database."""
    ...


# 9. SHARED PRIVATE FUNCTION (used by both public functions)
async def _verify_database_connection(
    our_stories_database: Session
) -> bool:
    """Verify database connection is active. Used by multiple operations."""
    ...
```

**Critical Rule:** Never place private functions before public functions (unless they are property getters/setters). The file must read top-to-bottom from abstraction to implementation detail.

**Rationale:** Readers should encounter the "what" before the "how". This structure enables understanding at the call-site without jumping around the file.

---

## 11. TypeScript/TSX Component Patterns

### 11.1 Component Naming and Structure

- **Components**: Use PascalCase for React components
- **Hooks**: Always start with "use"
- **Props Interfaces**: ComponentName + Props pattern
- **Generic Components**: Use proper generic constraints

```typescript
// Component Naming: PascalCase for components, camelCase for functions
const UserProfile: React.FC<UserProfileProps> = ({ user, onUpdate }) => {
  // Component implementation
};

// Hook Naming: Always start with "use"
const useUserData = (userId: string): UseUserDataResult => {
  // Hook implementation
};

// Props Interface Naming: ComponentName + Props
interface UserProfileProps {
  user: User;
  onUpdate: (user: User) => void;
  readonly mode: 'view' | 'edit';
}

// Generic Components
interface DataTableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  onRowClick?: (item: T) => void;
}

const DataTable = <T extends { id: string }>({
  data,
  columns,
  onRowClick
}: DataTableProps<T>) => {
  // Component implementation
};
```

### 11.2 TSX-Specific Patterns

```typescript
// Props Destructuring with Type Hints
const StoryCard: React.FC<StoryCardProps> = ({ 
  story, 
  onRead, 
  className = "" 
}) => {
  return (
    <div className={`story-card ${className}`}>
      <h3>{story.title}</h3>
      <p>{story.excerpt}</p>
      <button onClick={() => onRead(story.id)}>
        Read More
      </button>
    </div>
  );
};

// Event Handler Typing
const handleStoryClick = (storyId: string): void => {
  navigate(`/stories/${storyId}`);
};

// Forward Ref Pattern
const CustomInput = React.forwardRef<HTMLInputElement, CustomInputProps>(
  ({ placeholder, onChange }, ref) => {
    return (
      <input 
        ref={ref}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
);
```

**Rationale:** Consistent component patterns make React code more predictable and easier to maintain. Proper typing prevents runtime errors and improves IDE support.

---

## 12. TypeScript-Specific Type Patterns

### 12.1 Union Types and Discriminated Unions

```typescript
// Union Types and Discriminated Unions
type LoadingState = 'idle' | 'loading' | 'success' | 'error';

type ApiResponse<T> = 
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };

// Utility Types
type OptionalUser = Partial<User>;
type UserWithoutId = Omit<User, 'id'>;

// Generic Constraints
interface Repository<T extends { id: string }> {
  findById(id: string): Promise<T | null>;
  save(entity: T): Promise<T>;
}
```

### 12.2 Result Pattern for Error Handling

```typescript
// Result pattern for better error handling
type Result<T, E = Error> = 
  | { success: true; data: T }
  | { success: false; error: E };

async function fetchUserById(id: string): Promise<Result<User>> {
  try {
    const user = await ourUsersDatabase.findById(id);
    if (!user) {
      return { 
        success: false, 
        error: new UserNotFoundError(id) 
      };
    }
    return { success: true, data: user };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error : new Error(String(error)) 
    };
  }
}
```

**Rationale:** TypeScript's type system enables safer error handling and more expressive APIs. Union types and discriminated unions make state management more predictable.

---

## 13. TypeScript/TSX Import Organization

Order imports in four distinct groups, separated by blank lines:

```typescript
// 1. Node.js built-ins
import { promises as fs } from 'fs';
import path from 'path';

// 2. Third-party packages
import React from 'react';
import { z } from 'zod';
import axios from 'axios';

// 3. Internal packages (@/packages)
import { StoryResponse, User } from '@/shared/types';
import { ApiResponse } from '@/shared/utils';

// 4. App-specific imports (within current app)
import { OurStories } from '@/models';
import { useUserData } from '@/hooks';
import { UserProfile } from '@/components';
```

Within each group, sort alphabetically by module name.

**Rationale:** Consistent import organization makes dependencies clear and improves code navigation.

---

## 14. TypeScript Async Patterns

### 14.1 Async/Await Usage

**Use async for:**
- Database queries and API calls
- External HTTP requests
- File I/O operations
- LLM inference calls

**Use synchronous for:**
- Pure computation (scoring, sorting, filtering in-memory)
- Simple data transformations
- Hash calculations on small data

```typescript
// Use async for: API calls, database operations, file I/O
async function fetchUserData(userId: string): Promise<User> {
  const response = await fetch(`/api/users/${userId}`);
  return response.json();
}

// Use synchronous for: pure computation, data transformations
function calculateUserScore(user: User): number {
  return user.interests.length * user.activityLevel;
}

// Promise.all for concurrent operations
async function fetchUserAndStories(userId: string): Promise<[User, Story[]]> {
  return Promise.all([
    fetchUserData(userId),
    fetchUserStories(userId)
  ]);
}
```

**Never** use `asyncio.run()` inside application code—defer to FastAPI/Celery's event loops.

**Rationale:** Proper async usage prevents blocking operations and improves performance.

---

## 10. Explicit Error Handling

Errors must be handled explicitly. Never silently suppress exceptions. Always provide descriptive error messages and appropriate error types.

**Python:**
```python
from typing import Never

async def fetch_user_by_email_address(
    email_address: str,
    our_users_database: AsyncSession
) -> OurUsers:
    """Fetch a user by email address."""
    user_query: Query = our_users_database.query(OurUsers)
    email_filter: ColumnElement[bool] = OurUsers.email_address == email_address
    filtered_query: Query = user_query.filter(email_filter)
    found_user: OurUsers | None = await filtered_query.first()
    
    if found_user is None:
        raise UserNotFoundError(
            f"No user found with email address: {email_address}"
        )
    
    return found_user
```

**TypeScript/TSX:**
```typescript
// Custom error classes
class UserNotFoundError extends Error {
  constructor(email: string) {
    super(`No user found with email: ${email}`);
    this.name = 'UserNotFoundError';
  }
}

async function fetchUserByEmailAddress(
  email: string,
  ourUsersDatabase: DatabaseService
): Promise<User> {
  const user: User | null = await ourUsersDatabase.findByEmail(email);
  
  if (user === null) {
    throw new UserNotFoundError(email);
  }
  
  return user;
}
```

**Error Naming Conventions:**
- Use domain-specific error types (`UserNotFoundError`, `StoryNotFoundError`)
- Inherit from appropriate base classes (`Error`, custom `SpotmuException`)
- Include relevant identifiers in error messages
- Chain exceptions with proper error handling patterns

**Rationale:** Explicit error handling surfaces problems at the point of failure with full context. Silent failures create debugging nightmares.

---

## Summary Checklist

Before submitting code, verify:

**Core Rules (All Languages):**
- [ ] Every variable has a type hint
- [ ] Blank lines separate logical groups
- [ ] No chained operations—decomposed into named intermediates
- [ ] Full words used, no abbreviations
- [ ] Function names describe exact context (`_source_page_or_404`, not `_source_or_404`)
- [ ] Database classes/variables use `Our` prefix + plural (`OurStories`, not `Story`)
- [ ] Collections use plural names, single objects use singular
- [ ] Each function has one purpose; complex operations decomposed into private helpers
- [ ] File reads top-to-bottom: public functions before their private helpers
- [ ] All errors handled explicitly with descriptive messages

**Python-Specific:**
- [ ] Function parameters on same line as declaration (unless 6+ params); return type on next line
- [ ] Blank line between function signature and first body line
- [ ] Logic blocks (`if`/`else`, `try`/`finally`, etc.) separated by blank lines on both sides
- [ ] Return statements preceded by a blank line

**TypeScript/TSX-Specific:**
- [ ] Function parameters on same line as declaration (unless 6+ params); return type on same line
- [ ] Components use PascalCase, hooks start with "use"
- [ ] Props interfaces follow ComponentName + Props pattern
- [ ] Union types and discriminated unions used for state management
- [ ] Imports organized in 4 groups: Node.js built-ins, third-party, internal packages, app-specific
- [ ] Async/await used appropriately for I/O operations
- [ ] Event handlers properly typed

---

## Supplementary Guidelines (Lower Priority)

The following conventions support the core 10 rules but are considered secondary to immediate readability.

---

### A. Documentation Format

**Python:** Use Google-style docstrings for all public functions and classes.

```python
def calculate_affinity_score(
    story_embedding: list[float],
    interest_embedding: list[float]
) -> float:
    """Calculate cosine similarity between story and interest embeddings.

    Args:
        story_embedding: The 1536-dimensional embedding vector from the story.
        interest_embedding: The 1536-dimensional embedding vector from the interest.

    Returns:
        A float between -1.0 and 1.0 representing cosine similarity.
        Higher values indicate stronger semantic match.

    Raises:
        DimensionMismatchError: If embedding vectors have different lengths.
        ValueError: If either embedding contains non-numeric values.
    """
    ...
```

**TypeScript/TSX:** Use JSDoc comments for all public functions and components.

```typescript
/**
 * Calculates cosine similarity between story and interest embeddings.
 * 
 * @param storyEmbedding - The 1536-dimensional embedding vector from the story
 * @param interestEmbedding - The 1536-dimensional embedding vector from the interest
 * @returns A number between -1.0 and 1.0 representing cosine similarity
 * @throws {DimensionMismatchError} If embedding vectors have different lengths
 * @throws {Error} If either embedding contains non-numeric values
 */
function calculateAffinityScore(
  storyEmbedding: number[],
  interestEmbedding: number[]
): number {
  // Implementation
}

/**
 * Props for the UserProfile component
 */
interface UserProfileProps {
  /** The user object to display */
  user: User;
  /** Callback function called when user data is updated */
  onUpdate: (user: User) => void;
  /** Display mode for the component */
  readonly mode: 'view' | 'edit';
}

/**
 * A component that displays user profile information
 * 
 * @param props - The component props
 * @returns A React element representing the user profile
 */
const UserProfile: React.FC<UserProfileProps> = ({ user, onUpdate, mode }) => {
  // Component implementation
};
```

**Required elements for public functions/components:**
- One-line summary (imperative mood)
- Parameter descriptions with type information
- Return value explanation
- Exception/error information (if applicable)
- Usage examples for complex components

---

### B. Import Ordering

**Python:** Order imports in four distinct groups, separated by blank lines:

```python
# 1. Standard library imports
import datetime
from typing import Optional, Any
from pathlib import Path

# 2. Third-party package imports
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi import HTTPException

# 3. Internal package imports (from /packages)
from our_shared_types import StoryResponse
from our_validation_schemas import UserSchema

# 4. Application-specific imports (within current app)
from our_project.models import OurStories, OurUsers
from our_project.services import calculate_affinity_score
```

**TypeScript/TSX:** Order imports in four distinct groups, separated by blank lines:

```typescript
// 1. Node.js built-ins
import { promises as fs } from 'fs';
import path from 'path';

// 2. Third-party packages
import React from 'react';
import { z } from 'zod';
import axios from 'axios';

// 3. Internal packages (@/packages)
import { StoryResponse, User } from '@/shared/types';
import { ApiResponse } from '@/shared/utils';

// 4. App-specific imports (within current app)
import { OurStories } from '@/models';
import { useUserData } from '@/hooks';
import { UserProfile } from '@/components';
```

Within each group, sort alphabetically by module name.

---

### C. Maximum Line Length

**Soft limit: 120 characters.** Hard limit: 140 characters for complex type signatures.

The explicit type hinting and full word naming in this style guide produces longer lines than traditional code. A generous limit accommodates these without forcing unnatural breaks.

**Python:**
```python
# Prefer: Break after opening paren, align parameters
async def fetch_stories_with_complex_filtering(
    user_identifier: str,
    interest_identifiers: list[str],
    our_stories_database: Session,
    minimum_actionability_score: int = 5,
    maximum_story_age_hours: int = 48
) -> list[OurStories]:
    ...
```

**TypeScript/TSX:**
```typescript
// Prefer: Break after opening paren, align parameters
async function fetchStoriesWithComplexFiltering(
  userId: string,
  interestIds: string[],
  database: Database,
  minScore: number = 5,
  maxAge: number = 48
): Promise<Story[]> {
  // Implementation
}

// For complex generic types, consider type aliases
type UserStoryMap = Map<string, Story[]>;
type ApiResponseWithMetadata<T> = {
  data: T;
  metadata: {
    count: number;
    timestamp: Date;
  };
};
```

---

### D. Async/Await Patterns

**Use `async` for:**
- Database queries (SQLAlchemy async session)
- External HTTP API calls
- LLM inference calls
- File I/O operations

**Use synchronous for:**
- Pure computation (scoring, sorting, filtering in-memory)
- Simple data transformations
- Hash calculations on small data

**Never** use `asyncio.run()` inside application code—defer to FastAPI/Celery's event loops.

---

### E. Return Type Always Explicit

Every function must declare its return type, including `None` for void functions.

```python
# Correct
def mark_story_as_read(
    story_hash_id: str,
    our_stories_database: Session
) -> None:
    """Mark a story as read. Returns nothing."""
    ...

async def fetch_story_count(
    our_stories_database: Session
) -> int:
    """Return total count of stories in database."""
    ...

# Incorrect (missing return type and type hints)
def mark_story_as_read(story_id, db):
    ...
```

---

*End of Style Guide v1.1.0*

## TypeScript/TSX Adaptations Summary

The core principles of this style guide apply equally to Python, TypeScript, and TSX. The key adaptations are:

1. **Function Signatures**: Return types stay on the same line in TypeScript
2. **Component Patterns**: PascalCase for components, "use" prefix for hooks
3. **Type Patterns**: Union types, discriminated unions, and Result patterns
4. **Import Organization**: 4-group system with Node.js built-ins first
5. **Documentation**: JSDoc instead of docstrings for TypeScript

All other rules (type clarity, full words, single responsibility, etc.) remain identical across languages.
