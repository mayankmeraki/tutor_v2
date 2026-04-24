"""
Enrich all 15 System Design problems in MongoDB with interview-grade depth content.

Usage:  python enrich_sd_problems.py
"""

import os, certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
client = MongoClient(os.environ["MONGODB_URI"], tlsCAFile=certifi.where())
db = client[os.environ.get("MONGODB_DB", "capacity")]
col = db["sd_problems"]

# ---------------------------------------------------------------------------
# ENRICHMENTS — every field is problem-specific, no generic filler
# ---------------------------------------------------------------------------

ENRICHMENTS = {

    # -----------------------------------------------------------------------
    # 1. URL SHORTENER
    # -----------------------------------------------------------------------
    "url-shortener": {
        "level_expectations": {
            "mid": "Should identify the core read-heavy access pattern (~100:1 read/write), propose a hash/counter-based ID scheme, and sketch a basic cache layer in front of the DB.",
            "senior": "Must compare hash-truncation vs Base62-encoded counter trade-offs, design a multi-tier caching strategy (local + Redis), address DB sharding by short-code prefix, and handle TTL expiry with lazy + active cleanup.",
            "staff": "Expected to reason about collision probability math (birthday paradox at scale), design a globally unique ID generation layer (Snowflake/TSID), plan analytics pipelines for click tracking, and discuss abuse prevention (spam URLs, phishing detection)."
        },
        "edge_cases": [
            "Hash collision when two different long URLs produce the same truncated hash — need retry or append-counter logic",
            "Custom alias conflicts: user requests a short code that already exists for a different URL",
            "Concurrent writes for the same long URL — two requests arrive simultaneously, both try to insert",
            "URL with query parameters vs without: should https://x.com?ref=a and https://x.com?ref=b get the same short code?",
            "Expired short code reuse — a TTL'd link expires, new link gets the same code, but old cached redirects still exist",
            "Extremely long URLs exceeding database column limits (some URLs are 2000+ chars)",
            "International domain names (IDN) with punycode — normalization before hashing",
            "Redirect loop: shortened URL points to another shortened URL which points back"
        ],
        "follow_ups": [
            "How would you add real-time click analytics (clicks per second, geographic distribution) without slowing down redirects?",
            "Design a preview feature that shows the destination URL and safety info before redirecting.",
            "How would you handle a celebrity tweeting a shortened link causing 1M clicks/sec?",
            "What changes if you need to support private/authenticated short links?",
            "How would you implement URL expiry with both time-based and click-count-based limits?"
        ],
        "deep_dives": [
            {
                "topic": "ID Generation: MD5 Truncation vs Base62 Counter vs Snowflake",
                "why_important": "The short-code generation scheme determines collision rate, predictability, and scalability — it is the core design decision.",
                "key_points": [
                    "MD5 truncation (first 7 chars of Base62-encoded MD5): stateless, idempotent for same URL, but collisions require retry",
                    "Base62 counter (auto-increment ID encoded): no collisions, sequential, but requires a centralized counter or range allocation",
                    "Snowflake IDs: distributed, time-ordered, but longer codes (10-11 chars vs 7)",
                    "Hybrid: use counter with random offset per shard to avoid predictability"
                ],
                "trade_offs": "MD5 truncation gives idempotency (same URL = same code) but has O(1/62^7) collision probability. Counters guarantee uniqueness but need coordination. Snowflake avoids coordination but produces longer codes."
            },
            {
                "topic": "Read-Heavy Caching Architecture",
                "why_important": "With 100:1 read/write ratio, caching strategy directly determines latency and cost. A cache miss on every redirect makes the system unusable at scale.",
                "key_points": [
                    "L1: application-local in-memory cache (Guava/Caffeine) — eliminates network hop for hot URLs",
                    "L2: distributed Redis cluster — shared across app instances, handles warm URLs",
                    "L3: database with read replicas — fallback for cold URLs",
                    "Cache-aside pattern: read from cache first, populate on miss, invalidate on URL update/delete"
                ],
                "trade_offs": "Local cache is fastest but leads to inconsistency across instances when a URL is deleted. Redis adds a network hop but ensures consistency. Must balance TTL freshness with cache hit ratio."
            },
            {
                "topic": "Database Sharding Strategy",
                "why_important": "A single database becomes a bottleneck beyond ~50K writes/sec. Sharding strategy affects both write distribution and read efficiency.",
                "key_points": [
                    "Shard by short_code hash: even distribution, but range queries (analytics) require scatter-gather",
                    "Shard by short_code prefix (first 2 chars): predictable routing, 62^2 = 3844 logical shards",
                    "Shard by creation timestamp: good for TTL cleanup, but hot shard for recent writes",
                    "Cross-shard concern: checking custom alias uniqueness requires global lookup or reservation service"
                ],
                "trade_offs": "Hash-based sharding distributes evenly but makes analytics queries expensive. Prefix-based is predictable but may skew if certain prefixes are overrepresented."
            }
        ],
        "common_mistakes": [
            "Using a full UUID as the short code — defeats the purpose of shortening",
            "Not addressing hash collisions at all, assuming truncated hashes are unique",
            "Putting the analytics write in the redirect hot path, adding latency to every redirect",
            "Forgetting to handle the 301 vs 302 redirect trade-off (301 is cached by browsers, so you lose analytics)",
            "No rate limiting on URL creation — bot can exhaust the entire key space",
            "Ignoring cache invalidation when a URL is deleted or expires",
            "Designing for write-heavy when the workload is overwhelmingly reads"
        ],
        "solution_outline": {
            "entities": [
                "ShortURL: {short_code, long_url, user_id, created_at, expires_at, click_count}",
                "ClickEvent: {short_code, timestamp, ip_hash, user_agent, referer, country}",
                "User: {user_id, api_key, tier, rate_limit}"
            ],
            "api_sketch": [
                "POST /api/v1/urls  {long_url, custom_alias?, ttl?} -> {short_url, short_code}",
                "GET /{short_code}  -> 302 Redirect to long_url",
                "GET /api/v1/urls/{short_code}/stats  -> {clicks, top_countries, clicks_over_time}",
                "DELETE /api/v1/urls/{short_code}  -> 204"
            ],
            "components": [
                "API Gateway: rate limiting, authentication, routing",
                "URL Service: create/delete/lookup short URLs, ID generation",
                "Redirect Service: stateless, cache-heavy, optimized for sub-10ms p99",
                "Analytics Service: async click event ingestion via Kafka, rollup aggregation",
                "Cache Layer: local cache + Redis cluster in front of DB",
                "Database: sharded NoSQL (DynamoDB/Cassandra) or sharded MySQL"
            ],
            "data_flow": "Create: Client -> API Gateway -> URL Service -> generate short_code -> write DB -> invalidate cache -> return short_url. Redirect: Client -> Redirect Service -> check local cache -> check Redis -> check DB -> log click event to Kafka -> return 302. Analytics: Kafka -> Analytics Consumer -> aggregate in time-series DB -> serve via Stats API."
        },
        "teaching_notes": {
            "opening_question": "How many reads vs writes do you expect for a URL shortener, and how does that ratio shape your architecture?",
            "key_insight": "The system is fundamentally a distributed hash table with a 100:1 read/write ratio — every design decision should be optimized for read latency, not write throughput.",
            "scaffolding_hints": [
                "If they jump straight to database design, ask: 'What happens before the request even hits the database?'",
                "If they pick MD5 hashing, ask: 'What is the collision probability after 1 billion URLs?'",
                "If they forget analytics, ask: 'Why would a business want to shorten URLs in the first place?'",
                "If they use a single DB, ask: 'What is your read QPS and can one database handle it?'"
            ],
            "when_to_push": "Push when the candidate gives a surface-level caching answer ('just use Redis') without discussing cache invalidation, TTLs, or what happens on cache miss storms.",
            "when_to_help": "Help if they are stuck on the ID generation scheme — it is a well-known design space and struggling here wastes interview time that could be spent on more interesting trade-offs."
        }
    },

    # -----------------------------------------------------------------------
    # 2. TWITTER NEWS FEED
    # -----------------------------------------------------------------------
    "design-twitter-news-feed": {
        "level_expectations": {
            "mid": "Should identify the fan-out problem, propose a basic timeline table, and describe how following relationships form a social graph that drives feed generation.",
            "senior": "Must articulate fan-out on write vs read with concrete numbers, explain the celebrity problem (users with millions of followers), and design a ranking layer that goes beyond chronological ordering.",
            "staff": "Expected to design a hybrid fan-out strategy (write for normal users, read for celebrities), discuss timeline ranking with ML feature pipelines, handle real-time delivery via persistent connections, and plan for trends computation with streaming aggregation."
        },
        "edge_cases": [
            "Celebrity posts to 50M followers — fan-out on write would generate 50M timeline writes in seconds",
            "User unfollows someone — stale tweets from that user linger in pre-computed timeline cache",
            "Tweet deletion must propagate to all timelines that already contain it",
            "Protected/private accounts — fan-out must respect follow-approval status",
            "User follows 5000 accounts — fan-out on read at request time is slow, but fan-out on write is wasteful if user rarely checks",
            "Retweet chains: A retweets B who retweeted C — deduplication in timeline",
            "Time zone and ordering: tweets from different data centers arrive with clock skew"
        ],
        "follow_ups": [
            "How would you implement trending topics with a 5-minute sliding window over all tweets globally?",
            "Design the notification system for mentions, likes, and retweets — how does it differ from the feed?",
            "How would you add an algorithmic 'For You' feed alongside the chronological 'Following' feed?",
            "What changes if tweets can contain polls that update in real-time?",
            "How would you handle tweet threads (reply chains) in the feed without fragmenting the conversation?",
            "Design a system to detect and suppress bot-generated tweet storms in real-time."
        ],
        "deep_dives": [
            {
                "topic": "Fan-Out on Write vs Read (and the Hybrid Approach)",
                "why_important": "This is THE core design decision. It determines write amplification, read latency, and how you handle the celebrity problem — getting it wrong makes the system either slow or prohibitively expensive.",
                "key_points": [
                    "Fan-out on write: when user tweets, push tweet ID to all followers' timeline caches. Fast reads (O(1) timeline fetch), but write amplification for popular users",
                    "Fan-out on read: when user opens feed, pull tweets from all followed users and merge. No write amplification, but slow reads for users following many accounts",
                    "Hybrid (Twitter's actual approach): fan-out on write for users with <10K followers, fan-out on read for celebrities, merge at read time",
                    "Timeline cache is typically Redis sorted set: score=timestamp, value=tweet_id"
                ],
                "trade_offs": "Fan-out on write trades storage and write throughput for read latency. Fan-out on read trades read latency for write simplicity. The hybrid approach adds complexity but is the only viable solution at Twitter's scale (500M tweets/day)."
            },
            {
                "topic": "Timeline Ranking with ML",
                "why_important": "Chronological feeds bury important content under noise. Ranking directly affects engagement metrics, which drive the platform's business model.",
                "key_points": [
                    "Feature extraction: tweet engagement signals (likes, retweets, replies), author features (relationship strength, past interactions), content features (media, links, topic)",
                    "Two-pass ranking: lightweight candidate retrieval (1000 tweets) -> heavy ML scoring (top 200) -> final policy layer (dedup, diversity, ads insertion)",
                    "Real-time feature store: must serve features at <10ms for ranking pipeline",
                    "Feedback loop: user engagement (dwell time, likes, hides) feeds back into model training"
                ],
                "trade_offs": "Heavy ranking improves engagement but adds latency (50-100ms). Must balance relevance with recency — users expect to see breaking news immediately. Over-optimization for engagement can create filter bubbles."
            },
            {
                "topic": "Social Graph Storage and Traversal",
                "why_important": "The follow graph is the foundation of feed generation, recommendations, and trust/safety. It must support both point queries (does A follow B?) and range queries (all followers of B) at massive scale.",
                "key_points": [
                    "Adjacency list in distributed KV store: key=user_id, value=sorted list of followed user_ids",
                    "Separate 'following' and 'followers' lists for bidirectional traversal",
                    "Graph partitioning: shard by user_id, but celebrity nodes create hot partitions",
                    "Caching follower counts separately — avoid counting millions of edges on every profile view"
                ],
                "trade_offs": "Adjacency list is simple and fast for direct lookups but expensive for multi-hop queries (friend-of-friend). Graph databases (Neo4j) handle traversals better but are harder to shard. Most systems use adjacency lists with precomputed 2-hop caches for recommendations."
            },
            {
                "topic": "Real-Time Tweet Delivery",
                "why_important": "Users expect tweets to appear in feeds within seconds of posting. The delivery mechanism determines perceived freshness and infrastructure cost.",
                "key_points": [
                    "Persistent connections: WebSocket or Server-Sent Events (SSE) for open feed views",
                    "For users not currently online: write to timeline cache, they fetch on next open",
                    "Pub/Sub for real-time: tweet published to topic, subscribers with open connections get push",
                    "Connection management at scale: millions of concurrent WebSocket connections require specialized infrastructure (sticky sessions, connection registries)"
                ],
                "trade_offs": "Push via WebSocket gives instant delivery but maintaining millions of persistent connections is expensive. Poll-based approach is simpler but adds seconds of delay. Hybrid: push for active users, pull for returning users."
            }
        ],
        "common_mistakes": [
            "Using only fan-out on write without addressing the celebrity problem — a single Beyonce tweet would trigger 250M+ writes",
            "Designing a normalized SQL schema with JOIN-based feed generation — this cannot scale to millions of QPS",
            "Forgetting that timelines must be paginated and that 'load more' requires stable cursors, not OFFSET",
            "Not separating tweet storage from timeline cache — conflating the source of truth with the read-optimized view",
            "Ignoring tweet deletion propagation across pre-computed timelines",
            "Building ranking as an afterthought instead of designing the pipeline for it from the start",
            "Assuming all users are equal — not differentiating between a user with 50 followers and one with 50M"
        ],
        "solution_outline": {
            "entities": [
                "Tweet: {tweet_id (Snowflake), author_id, content, media_ids, created_at, reply_to, retweet_of}",
                "User: {user_id, handle, follower_count, following_count, is_celebrity (>10K followers)}",
                "Follow: {follower_id, followee_id, created_at}",
                "Timeline: {user_id, tweet_ids (sorted set in Redis)}"
            ],
            "api_sketch": [
                "POST /api/v1/tweets  {content, media_ids?, reply_to?} -> {tweet_id, created_at}",
                "GET /api/v1/timeline/home?cursor=X&limit=20 -> {tweets: [...], next_cursor}",
                "POST /api/v1/users/{id}/follow -> 200",
                "DELETE /api/v1/users/{id}/follow -> 200",
                "GET /api/v1/trends?region=US -> {trends: [{topic, tweet_count, velocity}]}"
            ],
            "components": [
                "Tweet Service: CRUD for tweets, stores in sharded database",
                "Fan-Out Service: on tweet create, pushes tweet_id to follower timelines (async via Kafka)",
                "Timeline Service: reads pre-computed timeline from Redis, merges celebrity tweets at read time, applies ranking",
                "Social Graph Service: follow/unfollow operations, follower/following lists",
                "Ranking Service: ML-based scoring of candidate tweets for personalized feed",
                "Trends Service: streaming aggregation (Flink/Spark Streaming) over tweet content",
                "Real-Time Delivery: WebSocket gateway for push delivery to active users"
            ],
            "data_flow": "Tweet: Author -> Tweet Service -> store tweet -> publish to Kafka -> Fan-Out Service reads author's follower list -> for non-celebrity: push tweet_id to each follower's Redis timeline -> for celebrity: skip (merge at read). Read: User -> Timeline Service -> fetch from Redis timeline -> merge celebrity tweets from Celebrity Cache -> Ranking Service scores and orders -> return paginated result."
        },
        "teaching_notes": {
            "opening_question": "If a user follows 500 people, how would you generate their home feed? Walk me through what happens when they open the app.",
            "key_insight": "The feed is not computed on the fly — it is a pre-materialized view that is incrementally maintained. The central tension is between write amplification (pre-compute) and read latency (compute on demand).",
            "scaffolding_hints": [
                "If they start with a SQL JOIN approach, ask: 'How many rows would that JOIN scan for a user following 500 people, each tweeting 10 times/day?'",
                "If they do fan-out on write only, ask: 'What happens when a user with 50M followers tweets?'",
                "If they skip ranking, ask: 'Should a tweet from your best friend and a tweet from a brand you followed once be treated equally?'",
                "If they forget real-time, ask: 'What happens when a user is staring at their feed and someone they follow tweets right now?'"
            ],
            "when_to_push": "Push when the candidate claims fan-out on write 'just works' without doing the math on write amplification, or when they hand-wave ranking as 'just add an ML model.'",
            "when_to_help": "Help if they are stuck on how to merge celebrity tweets at read time — walk them through the sorted-set merge of Redis timeline + per-celebrity tweet lists."
        }
    },

    # -----------------------------------------------------------------------
    # 3. INSTAGRAM
    # -----------------------------------------------------------------------
    "design-instagram-photo-sharing": {
        "level_expectations": {
            "mid": "Should design a basic photo upload and feed system with object storage (S3) for media, a relational schema for posts/users/follows, and a simple chronological feed.",
            "senior": "Must address the media processing pipeline (resize, compress, generate thumbnails), CDN distribution strategy, feed generation (fan-out), and the difference between feed and explore surfaces.",
            "staff": "Expected to design the full upload pipeline with async processing DAG, discuss CDN cache hierarchy and edge computing, handle ephemeral content (Stories with 24h TTL), and design the explore/recommendation system with embedding-based retrieval."
        },
        "edge_cases": [
            "Upload fails midway through a large video — need resumable uploads with chunked transfer",
            "Image contains EXIF GPS data that must be stripped for privacy before storage",
            "Viral post generates millions of requests to the same CDN object — origin shielding needed",
            "User deletes a post but CDN caches still serve it for hours due to TTL",
            "Story viewed at 23h59m — does it expire mid-view or after the session completes?",
            "Carousel post with 10 images — must be uploaded atomically (all or nothing)",
            "Duplicate photo detection — user uploads the same image twice accidentally",
            "HEIC/HEIF format from iPhones needs transcoding for Android/web compatibility"
        ],
        "follow_ups": [
            "How would you design the Explore page to show personalized content from accounts you do not follow?",
            "Design the image processing pipeline: what happens between upload and the photo appearing in feeds?",
            "How would you implement Instagram Reels with a TikTok-style recommendation algorithm?",
            "What changes when you add shopping tags that link product inventory to specific pixels in an image?",
            "How would you handle DMCA takedowns that must remove content globally within minutes?"
        ],
        "deep_dives": [
            {
                "topic": "Photo/Video Upload and Processing Pipeline",
                "why_important": "Media processing is the most resource-intensive operation and determines upload latency, storage cost, and viewing experience across devices. A poorly designed pipeline creates user-visible delays.",
                "key_points": [
                    "Client uploads original to a staging bucket (pre-signed URL for direct S3 upload, bypassing app server)",
                    "Upload triggers processing DAG: validate -> strip EXIF -> generate thumbnails (150px, 320px, 640px, 1080px) -> compress (WebP/AVIF) -> content moderation (NSFW detection) -> write manifest -> notify",
                    "Video: additional steps for transcoding (H.264/H.265), generating adaptive bitrate variants (360p, 720p, 1080p), extracting poster frame",
                    "Processing is async — app returns 202 Accepted, client polls or receives push notification when ready"
                ],
                "trade_offs": "Eager processing (generate all sizes upfront) wastes compute for sizes never requested but gives instant delivery. Lazy processing (generate on first request) saves compute but adds latency on first view. Instagram uses eager for common sizes, lazy for rare sizes."
            },
            {
                "topic": "CDN Distribution and Cache Hierarchy",
                "why_important": "With billions of photos served globally, CDN strategy directly determines latency (sub-100ms target) and bandwidth cost (which is the largest infrastructure expense).",
                "key_points": [
                    "Multi-tier: Edge PoP (200+ locations) -> Regional cache (10-20 locations) -> Origin shield (2-3 locations) -> S3 origin",
                    "Cache key includes image size variant and format negotiation (WebP for Chrome, JPEG for Safari)",
                    "Hot content (new posts from followed accounts) is proactively pushed to edge caches before users request it",
                    "Long-tail content (old posts) uses a higher TTL and tolerates cache misses"
                ],
                "trade_offs": "More edge locations reduce latency but increase storage and invalidation complexity. Proactive cache warming improves hit rate for popular content but wastes bandwidth if content is not actually viewed."
            },
            {
                "topic": "Stories: Ephemeral Content Architecture",
                "why_important": "Stories have fundamentally different access patterns than permanent posts — high write volume, short TTL, sequential viewing, and different privacy semantics (view-once, close-friends).",
                "key_points": [
                    "Stories tray: fetch list of users with active stories (expires_at > now), ordered by recency and relationship strength",
                    "Storage: same media pipeline but with TTL-based cleanup. Separate storage tier with aggressive lifecycle policies",
                    "View tracking: must record who viewed each story for the 'viewers' list — write-heavy at view time",
                    "Cleanup: cron job or TTL-based expiry in storage, but must also clean up CDN caches and database references"
                ],
                "trade_offs": "Using the same storage as permanent posts wastes money on content that lives only 24 hours. Separate ephemeral storage (Redis with TTL, or separate S3 bucket with lifecycle rules) reduces cost but adds architectural complexity."
            }
        ],
        "common_mistakes": [
            "Routing media uploads through the application server instead of using pre-signed URLs for direct-to-S3 upload",
            "Not designing for multiple image sizes — serving a 4K original to a thumbnail grid wastes bandwidth",
            "Synchronous image processing in the upload request — user waits 10+ seconds for resize/compress",
            "Forgetting content moderation in the pipeline — NSFW content must be caught before appearing in feeds",
            "Using a single global database for feed generation instead of region-aware fan-out",
            "Not distinguishing between the 'Following' feed (social graph) and 'Explore' feed (content-based recommendation)",
            "Ignoring the need for resumable uploads — mobile users on flaky connections lose large uploads"
        ],
        "solution_outline": {
            "entities": [
                "Post: {post_id, author_id, media_manifest (list of {url, width, height, format}), caption, location, created_at}",
                "Story: {story_id, author_id, media_url, created_at, expires_at, view_count, viewers: [user_ids]}",
                "User: {user_id, username, profile_pic_url, follower_count, bio}",
                "Follow: {follower_id, followee_id, created_at, is_close_friend}",
                "Like: {user_id, post_id, created_at}",
                "Comment: {comment_id, post_id, author_id, text, created_at, parent_comment_id}"
            ],
            "api_sketch": [
                "POST /api/v1/media/upload-url  {content_type, size} -> {upload_url, media_id}",
                "POST /api/v1/posts  {media_ids, caption, location?} -> {post_id}",
                "GET /api/v1/feed?cursor=X -> {posts: [...], next_cursor}",
                "GET /api/v1/stories/tray -> {users_with_stories: [{user_id, latest_story_ts, has_unseen}]}",
                "GET /api/v1/stories/{user_id} -> {stories: [...]}",
                "GET /api/v1/explore?category=X -> {posts: [...]}"
            ],
            "components": [
                "Upload Service: generates pre-signed URLs, tracks upload status",
                "Media Processing Pipeline: async DAG (resize, compress, moderate, store variants)",
                "Post Service: CRUD for posts, stores metadata in sharded DB",
                "Feed Service: fan-out on write for follows, ranked timeline in Redis/Memcached",
                "Stories Service: ephemeral content management, view tracking, TTL cleanup",
                "Explore/Recommendation Service: embedding-based retrieval, content-based filtering",
                "CDN: multi-tier cache with origin shielding for media delivery",
                "Notification Service: push notifications for likes, comments, follows, story mentions"
            ],
            "data_flow": "Upload: Client -> Upload Service -> pre-signed URL -> direct S3 upload -> S3 event triggers Media Processing Pipeline -> processed variants stored in S3 -> manifest written to DB -> client notified. Feed: User opens app -> Feed Service fetches pre-computed timeline from Redis -> hydrates post metadata from Post Service -> returns ranked, paginated feed."
        },
        "teaching_notes": {
            "opening_question": "Walk me through what happens from the moment a user taps 'Share' on a photo to when their followers see it in their feed.",
            "key_insight": "Instagram is fundamentally a media processing and distribution system — the hard problems are not in the social features (likes, comments) but in the upload pipeline, image processing DAG, and CDN distribution.",
            "scaffolding_hints": [
                "If they focus only on the database schema, redirect: 'Where do the actual image bytes live, and how do they get to the user's phone?'",
                "If they use synchronous processing, ask: 'What does the user see while their 10MB photo is being resized into 4 variants?'",
                "If they skip CDN, ask: 'How does a user in Tokyo load an image uploaded by a user in New York in under 100ms?'",
                "If they treat stories like posts, ask: 'What is different about content that disappears in 24 hours?'"
            ],
            "when_to_push": "Push when the candidate hand-waves media processing as 'just resize it' without discussing the async pipeline, format negotiation, or content moderation step.",
            "when_to_help": "Help if they are unfamiliar with pre-signed URLs or CDN architecture — these are infrastructure concepts that not everyone has worked with, and struggling here wastes time."
        }
    },

    # -----------------------------------------------------------------------
    # 4. CHAT (WHATSAPP)
    # -----------------------------------------------------------------------
    "design-chat-system-whatsapp": {
        "level_expectations": {
            "mid": "Should propose WebSocket-based messaging, a basic message store, and understand the need for online/offline handling with message queuing.",
            "senior": "Must design delivery receipts (sent/delivered/read), group messaging with fan-out, presence system, and offline message queue. Should discuss E2E encryption at a high level.",
            "staff": "Expected to design the Signal Protocol integration (double ratchet, prekey bundles), handle multi-device sync, design for global scale with data sovereignty requirements, and address message ordering guarantees across devices."
        },
        "edge_cases": [
            "Both users send a message at the exact same time — display ordering must be consistent on both devices",
            "User has the app open on phone and desktop simultaneously — messages must sync to both in real-time",
            "Recipient is offline for 30 days and comes back — must receive all queued messages in order without OOM",
            "Group of 256 members — one message triggers 255 deliveries, some members are offline",
            "User deletes a message 'for everyone' — must propagate deletion to all recipients, even offline ones",
            "Network partition: user sends messages on flaky connection — duplicates must be detected and suppressed",
            "Sending a 100MB video — chunked upload with progress, separate from the text message channel",
            "User blocks another user mid-conversation — delivery receipts must stop, presence must be hidden"
        ],
        "follow_ups": [
            "How would you implement E2E encryption such that even the server cannot read message content?",
            "Design the multi-device experience — messages sent from phone appear on desktop and vice versa.",
            "How would you handle voice and video calls using the same infrastructure?",
            "Design the backup system: how do users transfer chat history to a new phone?",
            "How would you implement disappearing messages with configurable TTL?"
        ],
        "deep_dives": [
            {
                "topic": "Real-Time Messaging via WebSocket",
                "why_important": "The choice of connection protocol determines message latency, battery impact on mobile devices, and server resource consumption for millions of concurrent connections.",
                "key_points": [
                    "Long-lived WebSocket (or MQTT for mobile) connection between client and edge gateway",
                    "Connection registry: in-memory map of user_id -> gateway_server_id for routing messages to the right server",
                    "Heartbeat mechanism to detect dead connections (30-60 second interval)",
                    "Reconnection with session resumption: client sends last_received_seq, server replays missed messages"
                ],
                "trade_offs": "WebSocket gives lowest latency but requires sticky connections and complicates load balancing. MQTT is more battery-efficient for mobile (binary protocol, smaller headers). Long polling is simpler but adds 100-500ms latency per message."
            },
            {
                "topic": "Message Delivery Receipts (Sent/Delivered/Read)",
                "why_important": "Delivery receipts (the checkmarks) are a core UX feature that requires a distributed state machine — each message transitions through states that must be tracked and communicated back to the sender.",
                "key_points": [
                    "States: Sent (single check) = server received; Delivered (double check) = recipient device received; Read (blue checks) = recipient opened chat",
                    "Sent: acknowledged by server on write to message store",
                    "Delivered: recipient's device sends ACK back through WebSocket, server forwards to sender",
                    "Read: recipient opens the chat, client sends read receipt for all unread messages up to a sequence number",
                    "Group receipts: track per-member delivery/read status, show aggregated status to sender"
                ],
                "trade_offs": "Tracking per-message, per-recipient status in a group of 256 creates 256 status records per message. Optimization: batch read receipts (mark all up to seq N as read) instead of per-message receipts."
            },
            {
                "topic": "Offline Message Queue",
                "why_important": "Users are frequently offline (subway, airplane, sleep). Messages sent to offline users must be durably queued and delivered in order when they reconnect, without losing any messages.",
                "key_points": [
                    "Per-user queue in persistent storage (Cassandra or DynamoDB), not just in-memory",
                    "Queue is drained on reconnect: client sends last_seq, server sends all messages with seq > last_seq",
                    "TTL on queued messages: messages older than 30 days are discarded (configurable)",
                    "Queue size limit: if queue exceeds threshold, oldest messages are tombstoned with 'message expired' placeholder",
                    "Priority: text messages delivered before media download links"
                ],
                "trade_offs": "Durable queue (Cassandra) survives server restarts but adds write latency. Redis-based queue is faster but risks data loss on crash. WhatsApp uses a write-ahead log approach — persist first, then attempt delivery."
            },
            {
                "topic": "End-to-End Encryption (Signal Protocol)",
                "why_important": "E2E encryption is a legal and trust differentiator. It fundamentally changes the architecture because the server cannot read, index, or process message content.",
                "key_points": [
                    "Key exchange: each device publishes a prekey bundle (identity key, signed prekey, one-time prekeys) to the server",
                    "Sender retrieves recipient's prekey bundle, performs X3DH (Extended Triple Diffie-Hellman) to establish shared secret",
                    "Double Ratchet: each message uses a new symmetric key derived from ratcheting the shared secret — forward secrecy",
                    "Server stores only encrypted ciphertext — cannot read content, but can see metadata (who messaged whom, when)"
                ],
                "trade_offs": "E2E encryption prevents server-side features like search, spam detection, and content moderation. Group E2E is significantly more complex (Sender Keys protocol). Multi-device requires key sharing between devices."
            }
        ],
        "common_mistakes": [
            "Using HTTP polling instead of persistent connections — unacceptable latency for real-time chat",
            "Storing messages only in a queue and not in a persistent message store — messages are lost if queue is consumed",
            "Not handling message ordering — messages from different senders can arrive out of order without vector clocks or sequence numbers",
            "Ignoring the group messaging fan-out problem — sending to 256 members is not the same as 1:1",
            "Treating presence (online/offline) as a simple boolean without considering privacy settings and stale state",
            "Designing E2E encryption as an application-layer wrapper instead of a protocol-level integration",
            "Forgetting idempotency — network retries can cause duplicate message delivery without dedup by message_id"
        ],
        "solution_outline": {
            "entities": [
                "Message: {message_id (client-generated UUID), conversation_id, sender_id, encrypted_content, timestamp, seq_num, status (sent/delivered/read)}",
                "Conversation: {conversation_id, type (1:1/group), participants, last_message_at}",
                "User: {user_id, phone_number, devices: [{device_id, push_token, prekey_bundle}], last_seen}",
                "GroupMembership: {group_id, user_id, role (admin/member), joined_at}"
            ],
            "api_sketch": [
                "WebSocket /ws/connect  {auth_token} -> persistent bidirectional connection",
                "WS Send: {type: 'message', conversation_id, encrypted_content, client_msg_id}",
                "WS Receive: {type: 'message', from, encrypted_content, timestamp, seq}",
                "WS Receive: {type: 'receipt', message_id, status: 'delivered'|'read'}",
                "GET /api/v1/messages/{conversation_id}?before=seq&limit=50 -> {messages: [...]}",
                "GET /api/v1/keys/{user_id}/prekey-bundle -> {identity_key, signed_prekey, one_time_prekey}"
            ],
            "components": [
                "WebSocket Gateway: manages persistent connections, connection registry, heartbeats",
                "Message Router: looks up recipient's gateway server, forwards encrypted message",
                "Message Store: append-only log per conversation (Cassandra/HBase), sharded by conversation_id",
                "Offline Queue: per-user queue for messages when recipient is disconnected",
                "Presence Service: tracks online/offline/last_seen, publishes presence events to contacts",
                "Key Distribution Service: stores and serves prekey bundles for E2E encryption",
                "Group Service: manages membership, fans out messages to group members",
                "Media Service: handles file upload/download with pre-signed URLs, separate from message channel"
            ],
            "data_flow": "Send: Sender device encrypts with Signal Protocol -> sends via WebSocket to Gateway -> Message Router checks connection registry -> if recipient online: forward to their Gateway -> recipient ACKs (delivered) -> if offline: write to Offline Queue -> recipient reconnects -> drain queue in order. Group: Sender encrypts with Sender Key -> Gateway fans out to each group member's route independently."
        },
        "teaching_notes": {
            "opening_question": "When you send a WhatsApp message and see the single checkmark, then double checkmark, then blue checkmark — what is happening at each stage between the two devices?",
            "key_insight": "Chat is a message routing problem with persistent connections and durable queuing. The key challenge is not the messaging itself but the guarantees: exactly-once delivery, ordering, and low latency — all across unreliable mobile networks.",
            "scaffolding_hints": [
                "If they use HTTP, ask: 'How does the recipient's phone know a new message arrived without polling every second?'",
                "If they ignore offline, ask: 'What happens to messages sent while the recipient is on airplane mode for 8 hours?'",
                "If they skip delivery receipts, ask: 'How does the sender know their message was actually delivered vs lost?'",
                "If they store messages in Redis only, ask: 'What happens if the Redis instance restarts?'"
            ],
            "when_to_push": "Push when the candidate treats group chat as trivially the same as 1:1 chat, or when they claim E2E encryption is 'just encrypt the payload with AES' without discussing key exchange.",
            "when_to_help": "Help if they are unfamiliar with WebSocket mechanics — explain the upgrade handshake and bidirectional nature so they can focus on the system design rather than protocol details."
        }
    },

    # -----------------------------------------------------------------------
    # 5. RATE LIMITER
    # -----------------------------------------------------------------------
    "design-rate-limiter": {
        "level_expectations": {
            "mid": "Should explain the token bucket or fixed window algorithm, implement it with a local counter, and discuss how to identify clients (API key, IP address).",
            "senior": "Must compare at least 3 algorithms (token bucket, sliding window log, sliding window counter) with trade-offs, design distributed rate limiting using Redis, and handle edge cases like clock synchronization and race conditions.",
            "staff": "Expected to design a hierarchical rate limiting system (per-user, per-endpoint, global), discuss exactly-once enforcement with Redis Lua scripts, handle graceful degradation under load, and design the rule configuration system for dynamic policy changes."
        },
        "edge_cases": [
            "Two requests arrive at the same millisecond from the same client — race condition on counter increment without atomic operations",
            "Client sends requests from multiple geographic regions — distributed counters may allow overshoot before syncing",
            "Clock skew between rate limiter nodes causes inconsistent window boundaries",
            "API key is shared across a microservice fleet — 100 instances each think they have the full quota",
            "Rate limit reset at window boundary causes thundering herd — all throttled clients retry simultaneously",
            "Client sends exactly the limit number of requests at the end of window 1 and start of window 2 — 2x burst in 1-second span with fixed windows",
            "Redis failover: what happens to rate limiting during a 3-second Redis cluster failover?"
        ],
        "follow_ups": [
            "How would you implement tiered rate limits: free users get 100 req/min, paid get 1000, enterprise gets 10000?",
            "Design a rate limiter that also shapes traffic (delays requests instead of rejecting them).",
            "How would you add cost-based rate limiting where different endpoints consume different amounts of quota?",
            "What if you need to rate limit WebSocket messages, not just HTTP requests?",
            "How would you implement a global rate limit shared across all users (e.g., 1M total API calls/min for the whole platform)?"
        ],
        "deep_dives": [
            {
                "topic": "Algorithm Comparison: Token Bucket vs Sliding Window vs Fixed Window",
                "why_important": "The algorithm choice determines burst behavior, memory usage, and implementation complexity. Picking the wrong algorithm can either waste capacity or allow dangerous traffic spikes.",
                "key_points": [
                    "Fixed window: simple counter per time window, but allows 2x burst at window boundary (e.g., 100 at 0:59 + 100 at 1:00)",
                    "Sliding window log: stores timestamp of each request, exact but O(n) memory per client",
                    "Sliding window counter: weighted average of current and previous window counts — approximate but O(1) memory",
                    "Token bucket: tokens refill at fixed rate, bucket has max capacity for burst — most flexible, used by AWS and Stripe"
                ],
                "trade_offs": "Token bucket allows controlled bursts (good UX) but requires two parameters (rate + burst). Sliding window counter is the best balance of accuracy and memory. Fixed window is simplest but the boundary burst problem is a real security concern."
            },
            {
                "topic": "Distributed Rate Limiting with Redis",
                "why_important": "In a multi-instance deployment, local rate limiting is useless — a client can spread requests across instances. Centralized enforcement via Redis is the industry standard but introduces network latency and failure modes.",
                "key_points": [
                    "Redis INCR + EXPIRE for fixed window: INCR key, if new key then EXPIRE N",
                    "Race condition: between INCR and EXPIRE, key could be set without expiry — use Lua script or MULTI/EXEC for atomicity",
                    "Token bucket in Redis: store {tokens, last_refill_time}, compute tokens to add based on elapsed time, all in a Lua script",
                    "Redis Cluster: shard by client_id ensures all requests from one client hit the same shard"
                ],
                "trade_offs": "Redis adds 0.5-2ms latency per request for the rate limit check. Local caching of rate limit state (check locally, sync to Redis periodically) reduces latency but allows temporary overshoot. Redis failure: must decide between fail-open (allow all) or fail-closed (block all)."
            },
            {
                "topic": "Graceful Degradation and Client Communication",
                "why_important": "How you reject rate-limited requests affects client behavior and system stability. Poor rejection handling causes retry storms that make congestion worse.",
                "key_points": [
                    "Return 429 Too Many Requests with Retry-After header indicating when the client can retry",
                    "Include X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers in ALL responses (not just 429s)",
                    "Exponential backoff guidance in documentation — clients without backoff will hammer the endpoint",
                    "Queue-based throttling: instead of rejecting, delay the request (traffic shaping) — better UX but requires more server resources"
                ],
                "trade_offs": "Rejecting immediately (429) is simple and protects the server but creates a bad client experience. Queuing and delaying is friendlier but consumes server memory and connections. The right choice depends on whether the system is protecting itself (reject) or managing fair access (shape)."
            }
        ],
        "common_mistakes": [
            "Implementing rate limiting only at the application level, not at the API gateway — every instance enforces independently, allowing N*limit total",
            "Using fixed window without acknowledging the boundary burst problem",
            "INCR and EXPIRE as separate Redis commands without atomicity — race condition can create keys that never expire",
            "Not returning proper 429 response with Retry-After header — clients cannot implement intelligent backoff",
            "Failing to distinguish between rate limiting (protecting the server) and throttling (fair usage) — different goals require different approaches",
            "Using IP address as the sole client identifier — NAT can put thousands of users behind one IP, and VPNs let one user appear as many",
            "No fallback strategy when Redis is down — the system either blocks all traffic or allows unlimited traffic"
        ],
        "solution_outline": {
            "entities": [
                "RateLimitRule: {rule_id, client_tier, endpoint_pattern, algorithm, limit, window_seconds, burst_capacity}",
                "RateLimitCounter: {client_id, rule_id, window_key, count, last_refill (for token bucket)}",
                "Client: {client_id, api_key, tier (free/paid/enterprise), custom_limits}"
            ],
            "api_sketch": [
                "Internal: CHECK_RATE_LIMIT(client_id, endpoint) -> {allowed: bool, remaining: int, reset_at: timestamp}",
                "Response Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset",
                "429 Response: {error: 'rate_limit_exceeded', retry_after: seconds}",
                "Admin: PUT /api/v1/rate-limits/rules/{rule_id} -> update rate limit configuration",
                "Admin: GET /api/v1/rate-limits/usage/{client_id} -> current usage across all rules"
            ],
            "components": [
                "Rate Limiter Middleware: intercepts every request at API Gateway, checks rate limit before forwarding",
                "Redis Cluster: stores counters/tokens, executes Lua scripts for atomic operations",
                "Rule Engine: loads rate limit rules from config DB, supports hot-reload without restart",
                "Monitoring: tracks 429 rate, per-client usage, Redis latency for alerting",
                "Local Cache: per-instance cache for rate limit rules (not counters) to avoid DB lookup on every request"
            ],
            "data_flow": "Request arrives at API Gateway -> Rate Limiter Middleware extracts client_id (from API key or IP) -> loads applicable rules from local cache -> executes Redis Lua script: compute current token count, decrement if allowed, return remaining -> if allowed: forward request, add rate limit headers to response -> if denied: return 429 with Retry-After."
        },
        "teaching_notes": {
            "opening_question": "Why can't we just use a simple counter in the application server to rate limit? What breaks when we have multiple servers?",
            "key_insight": "Rate limiting is fundamentally an atomic read-modify-write problem in a distributed system. The hard part is not the algorithm — it is making it work correctly across multiple servers with minimal latency overhead.",
            "scaffolding_hints": [
                "If they pick only fixed window, ask: 'What happens if a client sends 100 requests at second 59 and 100 more at second 61?'",
                "If they do local rate limiting, ask: 'With 10 server instances, what is the actual effective limit?'",
                "If they use Redis without Lua scripts, ask: 'What happens if the server crashes between INCR and EXPIRE?'",
                "If they skip client identification, ask: 'How do you identify who is making the request?'"
            ],
            "when_to_push": "Push when the candidate does not address atomicity in the Redis implementation, or when they treat rate limiting as a solved problem without discussing failure modes (Redis down, clock skew).",
            "when_to_help": "Help if they are not familiar with Redis Lua scripting — explain that Lua scripts execute atomically on the Redis server and ask them to describe what the script should do logically."
        }
    },

    # -----------------------------------------------------------------------
    # 6. WEB CRAWLER
    # -----------------------------------------------------------------------
    "design-web-crawler": {
        "level_expectations": {
            "mid": "Should describe BFS traversal of URLs, a queue for frontier management, and basic HTML parsing for link extraction. Should mention robots.txt.",
            "senior": "Must design the URL frontier with priority queue (freshness, importance), implement politeness policies (per-host crawl delay), handle deduplication at both URL and content level, and discuss distributed crawling across multiple workers.",
            "staff": "Expected to design a large-scale distributed crawler with DNS resolution caching, URL normalization strategies, content fingerprinting (SimHash for near-duplicate detection), incremental crawling with change detection, and crawl budget allocation."
        },
        "edge_cases": [
            "Spider trap: dynamically generated infinite URLs (e.g., calendar with next-month links forever)",
            "Soft 404: page returns 200 OK but content is actually a 'page not found' message",
            "URL with session ID in query string creates infinite unique URLs for the same content",
            "robots.txt changes mid-crawl — previously allowed pages become disallowed",
            "Page requires JavaScript rendering (SPA) — raw HTML has no useful content",
            "Extremely slow server: 30-second response time ties up a crawler thread",
            "Redirect chains: A -> B -> C -> D, with D redirecting back to A (redirect loop)",
            "Same content at multiple URLs (www vs non-www, HTTP vs HTTPS, trailing slash vs not)"
        ],
        "follow_ups": [
            "How would you detect and avoid crawling dynamically generated spider traps?",
            "Design the re-crawling strategy: how do you decide which pages to re-crawl and how often?",
            "How would you handle JavaScript-rendered pages that require a headless browser?",
            "Design a focused crawler that only crawls pages related to a specific topic.",
            "How would you estimate the size of the web you have not yet crawled?"
        ],
        "deep_dives": [
            {
                "topic": "URL Frontier and Priority Queue",
                "why_important": "The frontier determines crawl order and efficiency. A naive BFS crawls billions of irrelevant pages before reaching important ones. Intelligent prioritization is what makes a crawler useful.",
                "key_points": [
                    "Two-level queue: front queue (priority) determines importance, back queue (politeness) ensures per-host rate limits",
                    "Priority signals: PageRank of the domain, freshness (how often the page changes), depth from seed URL",
                    "Back queue: one sub-queue per host, round-robin across hosts, with minimum delay between requests to the same host",
                    "Persistent frontier: too large for memory at web scale — backed by RocksDB or similar on-disk sorted store"
                ],
                "trade_offs": "Simple FIFO queue is easy but wastes crawl budget on low-value pages. Fully priority-sorted frontier is ideal but sorting billions of URLs is expensive. Mercator-style two-level architecture balances priority with politeness."
            },
            {
                "topic": "Deduplication: URL Normalization and Content Fingerprinting",
                "why_important": "Without deduplication, the crawler wastes bandwidth re-crawling the same content and pollutes downstream indexes with duplicates. URL-level dedup catches obvious cases; content-level catches mirrors and syndication.",
                "key_points": [
                    "URL normalization: lowercase host, remove default port, sort query params, remove tracking params (utm_*), resolve relative URLs",
                    "URL-level dedup: Bloom filter (probabilistic, O(1) lookup, small false positive rate) for seen URLs",
                    "Content fingerprinting: exact dedup via SHA-256 hash of page content",
                    "Near-duplicate detection: SimHash or MinHash — detects pages that are 95% similar (e.g., same article with different ads)"
                ],
                "trade_offs": "Bloom filter uses minimal memory but has false positives (might skip an unseen URL). Exact URL set uses more memory but is precise. Content fingerprinting catches more duplicates but requires downloading the page first."
            },
            {
                "topic": "Distributed Crawling Architecture",
                "why_important": "A single machine cannot crawl billions of pages. Distributing the crawl across thousands of workers introduces coordination challenges: how to split work, avoid duplicate crawling, and maintain politeness globally.",
                "key_points": [
                    "Partition by domain: consistent hashing assigns each domain to a specific worker — ensures politeness without global coordination",
                    "Central URL frontier vs distributed: central frontier is a bottleneck, distributed requires dedup coordination",
                    "DNS caching: resolve once per domain, share across workers — DNS lookup is often the slowest part of crawling",
                    "Checkpointing: each worker periodically saves its frontier state for crash recovery"
                ],
                "trade_offs": "Domain-based partitioning ensures politeness but creates hot workers for large domains (e.g., wikipedia.org). URL-based partitioning distributes more evenly but requires global politeness enforcement."
            }
        ],
        "common_mistakes": [
            "Not implementing robots.txt checking — this gets your crawler blocked and possibly legal action",
            "Using a simple in-memory set for URL deduplication — this exceeds memory at any meaningful scale",
            "Ignoring politeness: hammering a single host with 100 concurrent requests will get IP banned",
            "Not handling redirect chains, which can loop infinitely or exhaust connection resources",
            "Treating all pages as equally important — not implementing any priority in the crawl frontier",
            "Not accounting for JavaScript-rendered pages (SPAs) — the raw HTML may contain no useful content",
            "Synchronous single-threaded crawling — network I/O latency makes this absurdly slow"
        ],
        "solution_outline": {
            "entities": [
                "CrawlTask: {url, priority, domain, depth, discovered_at, last_crawled_at, etag, last_modified}",
                "CrawledPage: {url, content_hash, html_content, extracted_links, status_code, crawled_at}",
                "DomainPolicy: {domain, robots_rules, crawl_delay, last_request_at}",
                "URLFingerprint: {url_hash, content_simhash}"
            ],
            "api_sketch": [
                "Internal: ENQUEUE_URL(url, priority, source_url) -> {accepted: bool, reason}",
                "Internal: GET_NEXT_BATCH(worker_id, batch_size) -> {tasks: [CrawlTask]}",
                "Internal: REPORT_RESULT(task_id, {status_code, content_hash, extracted_links, duration})",
                "Admin: GET /api/v1/crawler/stats -> {pages_crawled, pages_queued, crawl_rate, errors}",
                "Admin: POST /api/v1/crawler/seeds -> add seed URLs to frontier"
            ],
            "components": [
                "URL Frontier: two-level priority + politeness queue, backed by RocksDB",
                "Fetcher Workers: async HTTP clients, respect robots.txt and crawl delays, handle redirects",
                "HTML Parser: extract links, text content, metadata (title, description, canonical URL)",
                "URL Normalizer: canonicalize URLs before dedup check",
                "Dedup Service: Bloom filter for URL-level, SimHash for content-level deduplication",
                "DNS Resolver Cache: shared DNS cache to avoid redundant lookups",
                "Content Store: store crawled pages in object storage (S3), metadata in database",
                "Coordinator: assigns domain partitions to workers, monitors health, rebalances on failure"
            ],
            "data_flow": "Seed URLs -> URL Frontier (prioritized) -> Coordinator assigns domain partitions to Workers -> Worker: check robots.txt cache -> resolve DNS (cached) -> fetch page -> parse HTML -> extract links -> dedup check (Bloom filter) -> enqueue new URLs to Frontier -> store crawled content -> report metrics. Re-crawl: Scheduler checks page freshness scores -> re-enqueues stale URLs with updated priority."
        },
        "teaching_notes": {
            "opening_question": "If you needed to crawl 1 billion web pages, what would be your biggest bottleneck — CPU, network, or something else?",
            "key_insight": "A web crawler is an I/O-bound distributed system where the hardest problems are not technical (fetching HTML is easy) but operational: politeness, deduplication, prioritization, and handling the adversarial nature of the web (spider traps, soft 404s, redirect loops).",
            "scaffolding_hints": [
                "If they start with sequential BFS, ask: 'How long would it take to crawl 1 billion pages at 1 page/second?'",
                "If they ignore robots.txt, ask: 'What happens legally and practically if you ignore a site's crawling policy?'",
                "If they use an in-memory set for dedup, ask: 'How much memory would 1 billion URLs consume?'",
                "If they skip prioritization, ask: 'Should a random blog post and the New York Times homepage be crawled with equal urgency?'"
            ],
            "when_to_push": "Push when the candidate treats the frontier as a simple queue without priority or politeness, or when they do not consider how to detect and escape spider traps.",
            "when_to_help": "Help if they are unfamiliar with Bloom filters or consistent hashing — these are building blocks that enable the design but are not the core of the problem."
        }
    },

    # -----------------------------------------------------------------------
    # 7. NOTIFICATION SYSTEM
    # -----------------------------------------------------------------------
    "design-notification-system": {
        "level_expectations": {
            "mid": "Should identify the multi-channel nature (push, email, SMS), propose a message queue for async delivery, and describe basic user preference management.",
            "senior": "Must design the priority queue system, handle deduplication (no duplicate notifications), implement retry with exponential backoff for failed deliveries, and discuss template engines for consistent formatting across channels.",
            "staff": "Expected to design the full event-driven architecture with topic routing, handle cross-channel coordination (e.g., don't push AND email for the same event), design analytics for delivery/open/click tracking, and address notification fatigue with intelligent batching and suppression."
        },
        "edge_cases": [
            "User has notifications disabled on iOS but enabled in app settings — must check both device and app-level preferences",
            "Same event triggers notifications from multiple services (e.g., friend likes AND comments) — must deduplicate or batch",
            "Push notification token expires (user reinstalled app) — delivery fails silently, must detect stale tokens",
            "Timezone-aware delivery: don't send promotional notifications at 3 AM in the user's local time",
            "User unsubscribes from email mid-flight — notification is already in the queue and gets delivered anyway",
            "SMS delivery to a number that has been ported to a different carrier — routing failure",
            "Rate limit exceeded on third-party push provider (APNs/FCM) — must queue and retry without losing messages"
        ],
        "follow_ups": [
            "How would you implement notification batching — grouping '5 friends liked your photo' into a single notification?",
            "Design a notification preference center where users can configure per-channel, per-category preferences.",
            "How would you A/B test notification content and measure impact on click-through rates?",
            "What changes if you need to support rich notifications with images and action buttons?",
            "Design a system to detect and prevent notification spam from abusive applications.",
            "How would you handle regulatory requirements like GDPR right-to-delete affecting notification history?"
        ],
        "deep_dives": [
            {
                "topic": "Priority Queue and Delivery Ordering",
                "why_important": "Not all notifications are equal — a security alert must arrive in seconds, while a weekly digest can wait hours. Priority determines user trust and system resource allocation.",
                "key_points": [
                    "Priority levels: CRITICAL (security alerts, 2FA codes) -> HIGH (direct messages, mentions) -> MEDIUM (likes, comments) -> LOW (promotional, recommendations)",
                    "Separate queues per priority: critical queue has dedicated consumers that never back up behind promotional volume",
                    "SLA per priority: critical <30s end-to-end, high <2min, medium <10min, low <1hr",
                    "Queue depth monitoring: alert if critical queue depth exceeds threshold"
                ],
                "trade_offs": "Separate physical queues per priority guarantees isolation but wastes resources when high-priority queues are empty. Single queue with priority tags is simpler but a flood of low-priority notifications can delay high-priority ones if consumer pool is shared."
            },
            {
                "topic": "Retry Logic and Failure Handling",
                "why_important": "Push providers (APNs, FCM) and email/SMS gateways fail transiently. Without proper retry logic, notifications are silently lost — which is unacceptable for critical alerts.",
                "key_points": [
                    "Exponential backoff: 1s, 2s, 4s, 8s, ... up to max 5 retries for transient failures",
                    "Circuit breaker: if a provider fails 50% in the last minute, stop sending and fall back to alternate channel",
                    "Dead letter queue: after max retries, move to DLQ for manual investigation",
                    "Distinguish transient (429, 503) from permanent (invalid token, unsubscribed) failures — don't retry permanent failures",
                    "Stale token detection: mark device token as invalid after repeated 'not registered' errors from APNs/FCM"
                ],
                "trade_offs": "Aggressive retry improves delivery rate but can amplify load during provider outages. Conservative retry (few attempts, long backoff) is safer but delays delivery. The right balance depends on notification priority."
            },
            {
                "topic": "Cross-Channel Coordination and Deduplication",
                "why_important": "Users receive notifications on multiple channels. Sending the same alert via push, email, AND SMS simultaneously is annoying. Intelligent coordination improves user experience and reduces cost.",
                "key_points": [
                    "Cascade strategy: try push first, if not delivered in 5 minutes then send email, if not opened in 1 hour then send SMS",
                    "Dedup key: hash of (user_id, event_type, entity_id, time_window) — same event does not trigger multiple notifications",
                    "Batching: group multiple events of the same type (e.g., '5 people liked your post') using a short delay window (30-60s)",
                    "Quiet hours: suppress non-critical notifications during user's nighttime hours, deliver in morning batch"
                ],
                "trade_offs": "Cascade delivery gives the best UX but delays notifications by the cascade wait time. Parallel delivery to all channels is fastest but spams the user. Batching reduces notification fatigue but delays individual event awareness."
            }
        ],
        "common_mistakes": [
            "Treating all notifications as equal priority — 2FA codes and promotional emails should not share a queue",
            "Synchronous delivery in the request path — the action that triggered the notification blocks until notification is sent",
            "Not handling APNs/FCM token invalidation — silently failing to deliver to devices that uninstalled the app",
            "No deduplication: multiple services triggering the same notification event causes duplicate delivery",
            "Ignoring user timezone for delivery timing — sending promotional pushes at 3 AM",
            "Building a monolithic notification service instead of a pluggable channel architecture",
            "Not tracking delivery analytics — no way to know what percentage of notifications are actually delivered/opened"
        ],
        "solution_outline": {
            "entities": [
                "NotificationEvent: {event_id, event_type, source_service, user_id, entity_id, payload, priority, created_at}",
                "NotificationRecord: {notification_id, event_id, user_id, channel (push/email/sms/in_app), status, sent_at, delivered_at, opened_at}",
                "UserPreference: {user_id, channel_preferences: {push: {enabled, quiet_hours}, email: {enabled, frequency}, sms: {enabled, critical_only}}, category_preferences: {likes: [push], comments: [push, email], security: [push, sms, email]}}",
                "DeviceToken: {user_id, device_id, platform (ios/android/web), push_token, is_valid, last_used}",
                "Template: {template_id, channel, event_type, subject_template, body_template, locale}"
            ],
            "api_sketch": [
                "Internal: POST /api/v1/notifications/send  {event_type, user_id, payload} -> {event_id}",
                "Internal: POST /api/v1/notifications/broadcast  {event_type, user_segment, payload} -> {batch_id}",
                "GET /api/v1/notifications/inbox?cursor=X -> {notifications: [...], unread_count}",
                "PUT /api/v1/notifications/preferences  {channel_preferences, category_preferences} -> 200",
                "POST /api/v1/notifications/{id}/read -> 200",
                "PUT /api/v1/devices/{device_id}/token  {push_token, platform} -> 200"
            ],
            "components": [
                "Event Ingestion: receives notification events from all services via Kafka/SNS",
                "Preference Engine: loads user preferences, determines which channels to use for each event",
                "Template Engine: renders notification content with localization and personalization",
                "Priority Router: routes to appropriate priority queue based on event type",
                "Channel Adapters: pluggable adapters for APNs (iOS push), FCM (Android push), SendGrid (email), Twilio (SMS)",
                "Delivery Tracker: records delivery status, handles retries, manages dead letter queue",
                "In-App Service: stores notifications for in-app notification center/inbox",
                "Analytics Pipeline: tracks delivery, open, and click-through rates per channel/category"
            ],
            "data_flow": "Trigger: Service publishes event to Kafka -> Event Ingestion consumer picks it up -> dedup check (same event_id or dedup key) -> Preference Engine checks user settings + quiet hours -> Template Engine renders for each channel -> Priority Router enqueues to appropriate priority queue -> Channel Adapter sends (push/email/SMS) -> on success: record delivery -> on failure: retry with backoff or escalate to next channel in cascade."
        },
        "teaching_notes": {
            "opening_question": "You get a like on your Instagram photo. Walk me through how that like becomes a push notification on your phone, an email in your inbox, and an entry in your in-app notification center.",
            "key_insight": "A notification system is an event-driven routing problem with user preferences as the routing rules. The hard part is not sending notifications — it is deciding WHEN, WHERE, and HOW MANY to send without overwhelming the user.",
            "scaffolding_hints": [
                "If they build a monolith, ask: 'How do you add a new channel like Slack or web push without modifying existing code?'",
                "If they ignore preferences, ask: 'What if the user only wants push for direct messages but email for everything else?'",
                "If they skip dedup, ask: 'What happens when 10 people like the same post in 30 seconds — does the user get 10 separate push notifications?'",
                "If they forget retry, ask: 'What happens if Apple's push notification service is down for 2 minutes?'"
            ],
            "when_to_push": "Push when the candidate designs a simple fire-and-forget system without delivery tracking, retry logic, or cross-channel coordination.",
            "when_to_help": "Help if they are unfamiliar with APNs/FCM push notification mechanics — briefly explain the token-based flow so they can focus on the system design."
        }
    },

    # -----------------------------------------------------------------------
    # 8. UBER
    # -----------------------------------------------------------------------
    "design-uber-ride-sharing": {
        "level_expectations": {
            "mid": "Should propose a location-update system for drivers, a matching algorithm that pairs nearby riders with drivers, and basic trip state management (requested, matched, in-progress, completed).",
            "senior": "Must discuss geospatial indexing (Geohash or QuadTree), design the matching algorithm with scoring (distance, ETA, driver rating), handle surge pricing based on supply/demand imbalance, and design the trip state machine with failure handling.",
            "staff": "Expected to compare geospatial index options (QuadTree vs Geohash vs H3), design real-time ETA computation with map-matching and traffic data, handle multi-city deployment with geo-routing, and discuss dispatch optimization (batched matching vs greedy)."
        },
        "edge_cases": [
            "Two riders request a ride at the same intersection at the same time — same driver gets matched to both",
            "Driver accepts a ride but their phone dies — trip is stuck in 'accepted' state forever without timeout",
            "GPS drift in urban canyons (downtown Manhattan) — driver appears to be on a parallel street",
            "Rider requests from inside a building — GPS accuracy is 50+ meters, driver cannot find them",
            "Surge pricing changes between when rider sees the estimate and when they confirm — price guarantee needed",
            "Driver is on a highway bridge and appears close (Euclidean) but is 15 minutes away (road distance)",
            "Cross-border ride: trip starts in one regulatory jurisdiction and ends in another"
        ],
        "follow_ups": [
            "How would you design the surge pricing algorithm to balance supply and demand in real-time?",
            "Design the ETA estimation system that accounts for current traffic, time of day, and road conditions.",
            "How would you implement ride-sharing (UberPool) where multiple riders share a vehicle?",
            "Design the driver payment system including tips, bonuses, and weekly payouts.",
            "How would you handle a city with 100K concurrent drivers sending location updates every 4 seconds?",
            "Design the safety features: trip sharing, emergency button, anomaly detection (unexpected route)."
        ],
        "deep_dives": [
            {
                "topic": "Geospatial Indexing: QuadTree vs Geohash vs H3",
                "why_important": "Finding nearby drivers efficiently is the core operation — it happens on every ride request. The geospatial index determines query latency, update cost, and accuracy of proximity search.",
                "key_points": [
                    "QuadTree: recursive spatial decomposition, adaptive resolution (dense areas get finer cells). Good for in-memory use, hard to distribute",
                    "Geohash: string-encoded grid cells, prefix-based proximity (shared prefix = nearby). Easy to index in databases, but edge cases at cell boundaries",
                    "H3 (Uber's choice): hexagonal grid, uniform neighbors (no corner-adjacency ambiguity), hierarchical resolution. Better distance approximation than rectangles",
                    "All three: trade off between cell size (resolution) and query radius — finer cells mean more precision but more cells to search"
                ],
                "trade_offs": "QuadTree is most memory-efficient for non-uniform distributions but is hard to partition across servers. Geohash is simplest and works with any database supporting prefix queries. H3 has the best geometric properties but requires a custom library and is less universally supported."
            },
            {
                "topic": "Driver-Rider Matching Algorithm",
                "why_important": "Matching quality directly affects rider wait time, driver utilization, and platform revenue. A naive nearest-driver approach leaves money on the table vs. optimized dispatch.",
                "key_points": [
                    "Greedy matching: for each rider request, find nearest available driver, assign immediately. Simple, fast, suboptimal globally",
                    "Batched matching: collect requests over a 2-second window, solve assignment optimization to minimize total wait time",
                    "Scoring function: weighted combination of distance/ETA, driver rating, vehicle type match, driver heading (already driving toward rider?)",
                    "Supply positioning: proactively suggest drivers move to high-demand areas before requests arrive"
                ],
                "trade_offs": "Greedy matching is O(1) per request but can be globally suboptimal (assigns a close driver to one rider when that driver was the only option for another nearby rider). Batched matching gives better global outcomes but adds 2-3 seconds of latency."
            },
            {
                "topic": "Trip State Machine",
                "why_important": "A ride goes through many states (requested, matched, driver-en-route, arrived, in-trip, completed, cancelled). Each transition triggers actions (billing, notifications, driver availability). Incorrect state management causes phantom trips, double charges, or stuck drivers.",
                "key_points": [
                    "States: REQUESTED -> MATCHED -> DRIVER_EN_ROUTE -> DRIVER_ARRIVED -> IN_TRIP -> COMPLETED/CANCELLED",
                    "Timeouts at each state: if driver does not accept in 15s, re-dispatch. If driver does not arrive in 10min, cancel and re-match",
                    "Cancellation rules: free cancel within 2 min of matching, fee after. Different rules for driver vs rider cancel",
                    "Exactly-once transitions: use optimistic locking (version number) to prevent race conditions on state changes"
                ],
                "trade_offs": "Strict state machine with timeouts prevents stuck trips but may cancel legitimate rides (e.g., driver stuck in traffic). Lenient timeouts allow more flexibility but risk poor rider experience with long waits."
            }
        ],
        "common_mistakes": [
            "Using Euclidean distance instead of road/driving distance — a driver across a river may be close on the map but 30 minutes away by road",
            "Not handling the case where multiple riders request the same driver simultaneously — requires atomic claim/lock on driver availability",
            "Designing a centralized matching system for all cities — Uber operates in 900+ cities, each needs localized dispatch",
            "Storing all driver locations in a single relational database table — cannot handle 100K updates/second",
            "Forgetting driver heading/direction — a driver 500m away but driving away is worse than one 1km away driving toward you",
            "Not implementing trip timeouts — if a driver's phone dies, the trip is stuck forever without a timeout mechanism",
            "Conflating surge pricing with dynamic pricing — surge is supply/demand, dynamic pricing also includes route-based and time-based factors"
        ],
        "solution_outline": {
            "entities": [
                "Driver: {driver_id, vehicle_info, current_location (lat/lng), h3_cell, status (available/on_trip/offline), heading, rating}",
                "Rider: {rider_id, current_location, payment_method, rating}",
                "Trip: {trip_id, rider_id, driver_id, pickup (lat/lng/address), dropoff, status, fare_estimate, actual_fare, surge_multiplier, state_history: [{state, timestamp}]}",
                "GeoCell: {h3_cell_id, driver_ids (set), demand_count, supply_count, surge_multiplier}"
            ],
            "api_sketch": [
                "POST /api/v1/rides/estimate  {pickup, dropoff} -> {fare_range, eta, surge_multiplier}",
                "POST /api/v1/rides/request  {pickup, dropoff, vehicle_type, payment_method} -> {trip_id, status}",
                "PUT /api/v1/drivers/location  {lat, lng, heading, speed} -> 200 (called every 4s)",
                "PUT /api/v1/trips/{id}/accept  (driver) -> {pickup_details}",
                "PUT /api/v1/trips/{id}/start  (driver at pickup) -> 200",
                "PUT /api/v1/trips/{id}/complete  (driver at dropoff) -> {fare}",
                "WebSocket /ws/trip/{id}  -> real-time trip status and driver location updates"
            ],
            "components": [
                "Location Service: ingests driver location updates (100K+ per second), updates geospatial index",
                "Geospatial Index: H3-based grid mapping driver locations, supports 'find drivers in nearby cells' query",
                "Matching Service: finds candidate drivers, scores them, assigns best match with atomic lock",
                "Trip Service: manages trip state machine, timeouts, state transitions",
                "Pricing Service: computes fare estimates and surge multipliers based on supply/demand per geo-cell",
                "ETA Service: computes estimated time of arrival using road network graph + real-time traffic",
                "Payment Service: charges rider on trip completion, handles tips and cancellation fees",
                "Real-Time Gateway: WebSocket server for live trip tracking (driver location, ETA updates)"
            ],
            "data_flow": "Ride Request: Rider -> API Gateway -> Matching Service -> query Geospatial Index for nearby available drivers -> score candidates (ETA, rating, heading) -> select best -> atomically claim driver (set status=on_trip) -> create Trip record -> notify driver via push -> driver accepts -> Trip transitions to DRIVER_EN_ROUTE -> driver location updates streamed to rider via WebSocket. Location Updates: Driver -> Location Service -> update Geospatial Index (move driver to new H3 cell) -> update supply count for Pricing Service."
        },
        "teaching_notes": {
            "opening_question": "A rider opens the app and sees 'Finding your driver...' — what happens in those 10-15 seconds between tapping 'Request' and being matched?",
            "key_insight": "Uber is fundamentally a real-time spatial matching marketplace. The core challenge is maintaining a live, queryable index of all driver locations and finding the optimal driver-rider pairing under time pressure, not just the nearest driver.",
            "scaffolding_hints": [
                "If they use a SQL query like 'SELECT * FROM drivers WHERE distance < 5km', ask: 'How do you compute distance efficiently across 100K drivers?'",
                "If they skip the geospatial index, ask: 'How would you answer the query: find all drivers within 3 km of this point, when you have 50K active drivers in the city?'",
                "If they ignore driver heading, ask: 'Is a driver 500m away driving in the opposite direction better than one 1km away heading toward you?'",
                "If they forget surge pricing, ask: 'What happens on New Year's Eve when demand is 10x supply?'"
            ],
            "when_to_push": "Push when the candidate uses a simplistic nearest-driver matching without considering ETA, heading, or global optimization. Also push if they don't discuss what happens when things go wrong (driver cancels, phone dies).",
            "when_to_help": "Help if they are unfamiliar with geospatial indexing concepts — briefly explain how Geohash/H3 converts 2D coordinates into a 1D index and let them design around it."
        }
    },

    # -----------------------------------------------------------------------
    # 9. YOUTUBE
    # -----------------------------------------------------------------------
    "design-youtube-video-streaming": {
        "level_expectations": {
            "mid": "Should describe video upload to object storage, a transcoding step to produce multiple resolutions, and basic video streaming via CDN. Should mention the video metadata database.",
            "senior": "Must design the transcoding pipeline as a DAG of tasks, explain adaptive bitrate streaming (HLS/DASH), discuss CDN architecture for video delivery, and address the comment system at scale.",
            "staff": "Expected to design the full upload-to-playback pipeline with resumable uploads, discuss video codec selection (H.264/VP9/AV1) trade-offs, design the recommendation engine architecture, handle live streaming alongside on-demand, and address copyright detection (Content ID)."
        },
        "edge_cases": [
            "User uploads a 4K 2-hour video (50GB) on a mobile connection — upload fails at 90%, need resumable upload",
            "Transcoding fails on one resolution variant — should partial success be served or should it retry the whole job?",
            "Viral video gets 10M views in first hour — CDN origin is overwhelmed before edge caches are warm",
            "Video contains copyrighted music — must be detected before the video becomes publicly available",
            "Live stream with 1M concurrent viewers — each viewer needs a separate ABR stream",
            "User uploads a video and immediately shares the link — transcoding is not done yet, what does the viewer see?",
            "Video with hardcoded subtitles in a non-Latin script — auto-caption system fails, need fallback",
            "Simultaneous upload of 10 videos by the same creator — quota management per user"
        ],
        "follow_ups": [
            "How would you design the video recommendation engine that keeps users watching?",
            "Design the Content ID system that detects copyrighted material in uploaded videos.",
            "How would you add live streaming support alongside the existing on-demand video platform?",
            "Design the comment system to handle threads with millions of comments on popular videos.",
            "How would you implement video chapters and timestamp navigation?",
            "Design a system to generate automatic thumbnails and suggest the most engaging one to the creator."
        ],
        "deep_dives": [
            {
                "topic": "Video Transcoding Pipeline (DAG of Tasks)",
                "why_important": "Transcoding is the most compute-intensive operation — a single 4K video can take hours of CPU time. The pipeline must be efficient, fault-tolerant, and produce all required output variants.",
                "key_points": [
                    "DAG structure: Upload -> Validate (format, duration, size) -> Split into chunks -> Parallel transcode each chunk into multiple resolutions (360p, 720p, 1080p, 4K) x multiple codecs (H.264, VP9) -> Merge chunks -> Generate thumbnails -> Extract audio track -> Content moderation -> Publish manifest",
                    "Chunk-based parallelism: split video into 10-second segments, transcode each independently, merge — reduces wall-clock time from hours to minutes",
                    "Fault tolerance: if one chunk fails, retry just that chunk, not the entire video",
                    "Priority queue: paid creators and trending videos get priority transcoding"
                ],
                "trade_offs": "More output variants (resolutions x codecs) means better viewer experience but exponentially more compute cost. VP9/AV1 give better compression (40% smaller files) but are 10x slower to encode than H.264. YouTube encodes H.264 first for fast availability, then adds VP9/AV1 later."
            },
            {
                "topic": "Adaptive Bitrate Streaming (HLS/DASH)",
                "why_important": "Viewers have different network conditions (fiber vs 3G) and devices (4K TV vs phone). Adaptive bitrate streaming automatically adjusts quality in real-time to prevent buffering while maximizing quality.",
                "key_points": [
                    "HLS (Apple) / DASH (standard): video is split into 2-10 second segments, each available in multiple quality levels",
                    "Manifest file (.m3u8 for HLS, .mpd for DASH): lists all available quality levels and segment URLs",
                    "Client-side ABR algorithm: monitors download speed, buffer level, and switches quality up/down between segments",
                    "Server-side: must store N segments x M quality levels for each video — storage multiplied by M"
                ],
                "trade_offs": "Shorter segments (2s) allow faster quality adaptation but increase manifest size and CDN request count. Longer segments (10s) reduce overhead but cause visible quality drops that last longer. YouTube uses 5-second segments as a balance."
            },
            {
                "topic": "CDN Architecture for Video Delivery",
                "why_important": "Video is YouTube's largest cost — streaming petabytes of video daily. CDN strategy determines latency, bandwidth cost, and origin server load.",
                "key_points": [
                    "Three-tier: Edge PoP (close to users, serves hot content) -> Regional cache (aggregates long-tail) -> Origin (S3/GCS, source of truth)",
                    "Video popularity follows Zipf distribution: top 10% of videos get 90% of views — these are always cached at edge",
                    "Pre-warming: when a popular creator uploads, proactively push to edge caches before viewers request it",
                    "Long-tail optimization: infrequently viewed videos are served from regional cache or origin, not edge"
                ],
                "trade_offs": "Caching everything at every edge PoP is impossible (petabytes of video). Caching only popular videos saves storage but adds latency for long-tail content. Predictive caching (pre-warm based on subscriber count and historical view patterns) balances cost and performance."
            },
            {
                "topic": "Recommendation Engine Architecture",
                "why_important": "Recommendations drive 70%+ of YouTube's views. The recommendation system directly determines user engagement, watch time, and advertising revenue.",
                "key_points": [
                    "Two-stage pipeline: candidate generation (retrieve 1000 candidates from billions of videos) -> ranking (score and order top 50)",
                    "Candidate generation: collaborative filtering (users who watched X also watched Y), content-based (similar topics/channels), and real-time signals (trending)",
                    "Ranking model: deep neural network with features like user watch history, video freshness, engagement rates, creator-viewer relationship",
                    "Feedback loop: user actions (watch time, like, skip, 'not interested') feed back into model training"
                ],
                "trade_offs": "Optimizing for watch time increases engagement but can create filter bubbles and promote sensational content. Balancing engagement with diversity and quality requires multi-objective optimization with explicit diversity constraints."
            }
        ],
        "common_mistakes": [
            "Streaming the original uploaded file instead of transcoded ABR segments — causes buffering on slow connections",
            "Synchronous transcoding: making the uploader wait until all resolutions are ready before publishing",
            "Not implementing resumable upload — users lose a 2-hour upload because of a brief network drop",
            "Storing all video data in a single datacenter — global users experience high latency",
            "Treating the comment system as trivial — YouTube videos can have millions of comments requiring pagination, threading, and spam filtering",
            "Not considering copyright detection before making videos public",
            "Using a single transcoding queue without priority — a viral video's re-encode waits behind 100K regular uploads"
        ],
        "solution_outline": {
            "entities": [
                "Video: {video_id, channel_id, title, description, tags, upload_status (processing/ready/failed), duration, thumbnail_urls, manifest_url, created_at, view_count}",
                "VideoSegment: {video_id, resolution, codec, segment_number, storage_url, duration_ms}",
                "Channel: {channel_id, owner_id, name, subscriber_count, total_views}",
                "Comment: {comment_id, video_id, author_id, text, parent_comment_id, created_at, like_count}",
                "WatchHistory: {user_id, video_id, watched_at, watch_duration, completion_percent}"
            ],
            "api_sketch": [
                "POST /api/v1/videos/upload-url  {filename, size, content_type} -> {upload_url, video_id}",
                "PUT /api/v1/videos/{id}/metadata  {title, description, tags, visibility} -> 200",
                "GET /api/v1/videos/{id} -> {video metadata, manifest_url, channel_info}",
                "GET /api/v1/videos/{id}/manifest.m3u8 -> HLS manifest with quality variants",
                "GET /api/v1/feed/home -> {videos: [...]} (personalized recommendations)",
                "GET /api/v1/videos/{id}/comments?cursor=X&sort=top -> {comments: [...]}",
                "POST /api/v1/videos/{id}/comments  {text, parent_id?} -> {comment_id}"
            ],
            "components": [
                "Upload Service: resumable upload handling, pre-signed URLs, upload progress tracking",
                "Transcoding Pipeline: DAG-based task executor (chunk, transcode, merge) on GPU instances",
                "Video Storage: object storage (S3/GCS) for segments, metadata in database",
                "Streaming Service: serves HLS/DASH manifests and segments, handles quality negotiation",
                "CDN: three-tier (edge/regional/origin) for video segment delivery",
                "Recommendation Service: candidate generation + ranking pipeline for personalized feeds",
                "Comment Service: threaded comments with pagination, spam filtering, moderation",
                "Analytics Service: view counts, watch time, engagement metrics, real-time dashboards for creators"
            ],
            "data_flow": "Upload: Creator -> Upload Service (resumable, direct-to-storage) -> upload complete event -> Transcoding Pipeline (split -> parallel transcode -> merge -> thumbnails -> moderation) -> update Video status to 'ready' -> generate HLS manifest -> notify creator. Watch: Viewer -> API -> Recommendation Service -> video page -> Streaming Service returns manifest -> player fetches segments from CDN -> segments flow: Edge cache (hit?) -> Regional cache -> Origin storage. Each segment request triggers analytics event."
        },
        "teaching_notes": {
            "opening_question": "A creator uploads a 4K video. Walk me through every step that happens before a viewer on a 3G phone connection can watch it without buffering.",
            "key_insight": "YouTube is a media processing and distribution platform where the upload pipeline is a complex DAG and the delivery system must adapt in real-time to each viewer's network conditions. The social features (comments, likes, subscriptions) are secondary to the core video infrastructure.",
            "scaffolding_hints": [
                "If they skip transcoding, ask: 'Can a phone on 3G stream a 4K file directly?'",
                "If they do single-resolution transcoding, ask: 'What happens when a viewer's bandwidth drops from 10Mbps to 1Mbps mid-video?'",
                "If they ignore the upload UX, ask: 'What does the creator see after uploading? Can viewers watch immediately or must they wait for transcoding?'",
                "If they treat CDN as a black box, ask: 'How does the CDN decide which videos to cache at which locations?'"
            ],
            "when_to_push": "Push when the candidate treats video as 'just another file to serve' without discussing transcoding, adaptive streaming, or the CDN caching strategy for large binary objects.",
            "when_to_help": "Help if they are unfamiliar with HLS/DASH concepts — explain that video is split into segments and the player downloads them one at a time, choosing the quality level based on current bandwidth."
        }
    },

    # -----------------------------------------------------------------------
    # 10. GOOGLE SEARCH
    # -----------------------------------------------------------------------
    "design-google-search": {
        "level_expectations": {
            "mid": "Should describe web crawling, building an inverted index, and basic query processing (tokenize query, look up in index, return matching documents). Should mention relevance ranking.",
            "senior": "Must explain inverted index construction (posting lists with positions), discuss PageRank or link-based ranking, design the query processing pipeline (tokenize, expand, retrieve, rank, snippet), and handle spell correction.",
            "staff": "Expected to design the full search stack: offline index building pipeline, online query serving with tiered index (in-memory hot, SSD warm, disk cold), ranking with ML (learning-to-rank), snippet generation, freshness vs. relevance trade-offs, and query understanding (intent classification, entity recognition)."
        },
        "edge_cases": [
            "Query 'apple' — is the user looking for the fruit, the company, or Apple Records? Ambiguous intent",
            "Query in a language the system has not indexed well — fall back to translation or show limited results",
            "New page published 5 minutes ago about breaking news — not yet in the index but highly relevant",
            "Query with typo: 'restraunt near me' — must correct to 'restaurant near me' without losing intent",
            "Very long query (50+ words) — query processing must handle gracefully without timeout",
            "Adversarial SEO: page stuffed with keywords to game ranking — must detect and penalize",
            "Duplicate content across many domains (syndicated articles) — should show the original source, not copies"
        ],
        "follow_ups": [
            "How would you handle real-time indexing so breaking news appears in results within minutes?",
            "Design the spell correction system — how do you suggest 'restaurant' when the user types 'restraunt'?",
            "How would you implement personalized search results based on user history and location?",
            "Design the Knowledge Graph panel that appears alongside search results.",
            "How would you detect and handle SEO spam at scale?",
            "Design the autocomplete/suggestion system that predicts queries as the user types."
        ],
        "deep_dives": [
            {
                "topic": "Inverted Index Construction and Storage",
                "why_important": "The inverted index is the data structure that makes search fast — it transforms the problem from 'scan all documents' to 'look up a word'. Index design determines query latency, storage cost, and feature capabilities (phrase search, proximity search).",
                "key_points": [
                    "Forward index: document_id -> list of terms. Inverted index: term -> list of (document_id, positions, term_frequency)",
                    "Posting list: sorted list of document IDs containing the term, with metadata (positions for phrase queries, TF for ranking)",
                    "Index building: MapReduce pipeline — map phase tokenizes documents, reduce phase merges posting lists per term",
                    "Compression: delta encoding of document IDs (store gaps instead of absolute IDs) + variable-byte encoding reduces posting list size by 3-5x",
                    "Sharding: partition index by document (each shard has full vocabulary for its documents) — query broadcasts to all shards, results merged"
                ],
                "trade_offs": "Storing positions in posting lists enables phrase search ('New York Times') but doubles index size. Document-partitioned sharding gives even load but requires scatter-gather. Term-partitioned sharding avoids scatter-gather but creates hot shards for common terms."
            },
            {
                "topic": "PageRank and Link-Based Ranking",
                "why_important": "Keyword matching alone is not enough — 'Barack Obama' matches millions of pages. PageRank uses the link structure of the web as a quality signal: pages linked by many high-quality pages are more relevant.",
                "key_points": [
                    "PageRank: iterative algorithm — each page starts with equal rank, distributes its rank to outgoing links, converge after 50-100 iterations",
                    "Damping factor (0.85): models random surfer who occasionally jumps to a random page instead of following links",
                    "Computed offline on the web graph (billions of nodes) — result is a static score per page, used as one ranking feature",
                    "Link spam: detect and discount link farms, paid links, reciprocal link schemes",
                    "Modern ranking: PageRank is just one of 200+ features in a learning-to-rank ML model"
                ],
                "trade_offs": "PageRank captures web-scale authority but is slow to update (batch computation on the entire web graph). Newer pages have no PageRank. Combining with freshness signals and user engagement metrics gives a more complete ranking."
            },
            {
                "topic": "Query Processing Pipeline",
                "why_important": "The pipeline from raw query string to ranked results involves multiple stages, each adding latency. The system must return results in <200ms, which constrains the design of every stage.",
                "key_points": [
                    "1. Query Understanding: tokenize, normalize (lowercase, stemming), spell correct, identify entities, classify intent",
                    "2. Query Expansion: add synonyms, related terms, acronym expansions to improve recall",
                    "3. Retrieval: look up posting lists for query terms, intersect (AND) or union (OR), apply early-termination heuristics",
                    "4. Scoring: compute relevance score using BM25 (term frequency, document length normalization) + PageRank + freshness + 200 other features",
                    "5. Re-ranking: apply ML model (learning-to-rank) on top-1000 candidates to produce final top-10",
                    "6. Snippet generation: extract the most relevant passage from each result document, highlight query terms"
                ],
                "trade_offs": "More pipeline stages improve result quality but add latency. Early termination (stop scoring after finding 1000 good candidates) saves time but may miss relevant results. Caching query results helps with popular queries but wastes memory on unique queries."
            }
        ],
        "common_mistakes": [
            "Proposing to scan all documents for each query — this is O(N) and takes minutes for billions of documents",
            "Ignoring the offline index building pipeline and focusing only on query serving",
            "Using TF-IDF alone for ranking without considering link-based authority or freshness",
            "Not discussing index sharding — a single machine cannot hold the index for billions of web pages",
            "Forgetting spell correction and query understanding — users frequently make typos and use ambiguous terms",
            "Treating search as a stateless lookup instead of a pipeline with multiple stages",
            "Not addressing the freshness problem — a pure batch-built index cannot surface breaking news"
        ],
        "solution_outline": {
            "entities": [
                "Document: {doc_id, url, title, body_text, crawled_at, page_rank, language, content_hash}",
                "InvertedIndex: {term -> PostingList: [{doc_id, positions: [int], term_frequency, field (title/body)}]}",
                "QueryLog: {query_string, user_id, results_shown, result_clicked, timestamp}",
                "SpellModel: {misspelling -> corrections with probabilities}"
            ],
            "api_sketch": [
                "GET /search?q=query&page=1&lang=en -> {results: [{title, url, snippet, favicon}], total_results, spell_suggestion, related_searches, knowledge_panel?}",
                "GET /suggest?q=partial_query -> {suggestions: [string]}",
                "GET /cached?url=X -> cached version of the page",
                "Internal: BUILD_INDEX(document_batch) -> update index shards",
                "Internal: COMPUTE_PAGERANK(web_graph) -> update PageRank scores"
            ],
            "components": [
                "Web Crawler: fetches pages, sends to indexing pipeline (see web-crawler design)",
                "Index Builder: MapReduce pipeline that builds inverted index from crawled documents",
                "Index Server: serves query lookups from sharded inverted index (in-memory + SSD)",
                "Query Processor: tokenization, spell correction, query expansion, intent classification",
                "Ranker: BM25 + PageRank + ML re-ranking to produce final ordered results",
                "Snippet Generator: extracts relevant text passages from documents, highlights query terms",
                "Spell Corrector: n-gram language model + edit distance for query correction",
                "Cache: query result cache for popular/repeated queries (LRU with TTL)"
            ],
            "data_flow": "Offline: Crawler fetches pages -> Index Builder tokenizes, builds posting lists -> shards distributed across Index Servers -> PageRank computed on web graph, scores attached to documents. Online: User query -> Query Processor (tokenize, spell correct, expand) -> broadcast to Index Server shards -> each shard retrieves and scores locally -> merge results from all shards -> Re-rank top-1000 with ML model -> Generate snippets for top-10 -> Return to user. Total latency target: <200ms."
        },
        "teaching_notes": {
            "opening_question": "When you type a query into Google and get results in 0.2 seconds across billions of web pages, what data structure makes that possible?",
            "key_insight": "Search is a pre-computation problem. The inverted index converts the question from 'which documents contain this word?' (requires scanning all documents) to 'look up this word in a dictionary' (O(1)). Everything else — ranking, snippets, spell correction — is refinement on top of this core structure.",
            "scaffolding_hints": [
                "If they start with a database LIKE query, ask: 'How long would LIKE '%query%' take on 100 billion rows?'",
                "If they skip ranking, ask: 'You found 10 million documents containing the word 'python' — which 10 do you show first?'",
                "If they ignore freshness, ask: 'A major news event happened 10 minutes ago — when do search results reflect it?'",
                "If they design a single-machine system, ask: 'How large is the inverted index for 100 billion web pages?'"
            ],
            "when_to_push": "Push when the candidate treats search as a simple lookup problem without discussing ranking, or when they propose a single ranking signal (just PageRank, or just TF-IDF) instead of a multi-signal approach.",
            "when_to_help": "Help if they are unfamiliar with inverted indexes — draw the example: 'documents: [d1='the cat sat', d2='the dog sat'] -> index: {the: [d1,d2], cat: [d1], dog: [d2], sat: [d1,d2]}' and let them generalize."
        }
    },

    # -----------------------------------------------------------------------
    # 11. DROPBOX
    # -----------------------------------------------------------------------
    "design-dropbox-file-storage": {
        "level_expectations": {
            "mid": "Should describe file upload/download with cloud storage, basic sync between devices via polling, and a file metadata database. Should mention chunked uploads for large files.",
            "senior": "Must design the chunked upload protocol with content-addressable storage (deduplication), implement conflict resolution for concurrent edits, discuss change detection using filesystem events, and handle efficient delta sync.",
            "staff": "Expected to design the full sync protocol with block-level deduplication, discuss the Block Index and content-addressable storage (CAS), design multi-device sync with vector clocks for conflict detection, handle bandwidth optimization (delta encoding, compression), and address the sync client's filesystem watcher architecture."
        },
        "edge_cases": [
            "Two users edit the same file simultaneously on different devices — conflict resolution needed",
            "User edits a file offline for 3 days and comes back online — large sync queue with potential conflicts",
            "File renamed while another device is uploading it — metadata and content changes interleave",
            "Symbolic link in the sync folder — should the link be synced or the target file?",
            "User syncs a folder with 500,000 files — initial scan and metadata sync overwhelm the client",
            "Large binary file (10GB VM image) changed — re-uploading entire file wastes bandwidth, need block-level diff",
            "File permissions changed but content did not — should this trigger a sync?",
            "Network drops during chunked upload at chunk 47 of 100 — resume without re-uploading first 46 chunks"
        ],
        "follow_ups": [
            "How would you implement selective sync — user chooses which folders to sync to a specific device?",
            "Design the sharing system: how do permissions, shared folders, and shared links work?",
            "How would you add real-time collaborative editing (Google Docs style) on top of the file sync system?",
            "Design the version history feature that lets users restore previous versions of any file.",
            "How would you handle syncing to a device with limited storage (phone vs desktop)?"
        ],
        "deep_dives": [
            {
                "topic": "File Sync Protocol: Chunked Upload with Content-Addressable Storage",
                "why_important": "Users expect file sync to work efficiently even with large files and slow connections. Chunked upload with content-addressable storage enables deduplication (don't upload blocks that already exist in the cloud) and resumability.",
                "key_points": [
                    "Split files into fixed-size blocks (4MB) or variable-size blocks (Rabin fingerprinting for content-defined chunking)",
                    "Hash each block (SHA-256) — the hash IS the address in storage (content-addressable storage)",
                    "Upload protocol: client sends list of block hashes -> server responds with which blocks it already has -> client uploads only missing blocks -> server assembles file from block references",
                    "Dedup: if two users upload the same file, blocks are stored once. If a 10GB file has 1 byte changed, only 1 block is re-uploaded"
                ],
                "trade_offs": "Fixed-size chunking is simpler but a single insertion shifts all subsequent block boundaries, causing unnecessary re-uploads. Content-defined chunking (Rabin fingerprint) handles insertions gracefully but is more CPU-intensive on the client."
            },
            {
                "topic": "Conflict Resolution: Last-Writer-Wins vs Merge",
                "why_important": "When two users edit the same file simultaneously on different devices, the system must detect the conflict and resolve it without losing data. Getting this wrong causes data loss, which is unacceptable for a file sync product.",
                "key_points": [
                    "Conflict detection: each file has a version vector (logical clock per device). If two edits have concurrent version vectors (neither is an ancestor of the other), it is a conflict",
                    "Last-writer-wins (LWW): simpler, but one user's changes are silently lost — acceptable only if users understand the risk",
                    "Conflicted copy: create 'filename (conflicted copy - Device - Date)' alongside the original — Dropbox's actual approach",
                    "Merge: for structured files (text), attempt automatic merge (3-way merge). For binary files, merge is impossible",
                    "Prevention: lock the file while editing (pessimistic), or use OT/CRDT for real-time collaboration (eliminates file-level conflicts)"
                ],
                "trade_offs": "Conflicted copies preserve all data but create file clutter that users must resolve manually. LWW is clean but loses data. Locking prevents conflicts but blocks collaboration. Real-time collaboration (Google Docs approach) eliminates conflicts entirely but requires a fundamentally different architecture."
            },
            {
                "topic": "Change Detection on the Client",
                "why_important": "The sync client must detect when a file changes on the local filesystem to trigger upload. Polling the entire file tree is slow and battery-draining. Efficient change detection is critical for the user experience.",
                "key_points": [
                    "Filesystem events: inotify (Linux), FSEvents (macOS), ReadDirectoryChangesW (Windows) — OS notifies the client of file changes",
                    "Debouncing: rapid writes (e.g., saving a file every second) should be batched — wait for a stable period before syncing",
                    "Full scan fallback: filesystem events can be dropped (buffer overflow). Periodic full scan (every 30 min) catches missed changes",
                    "Database of local state: SQLite DB mapping file path -> (size, mtime, block hashes) for quick comparison",
                    "Ignored patterns: .git, node_modules, .DS_Store — configurable ignore list to avoid syncing transient files"
                ],
                "trade_offs": "Filesystem events are efficient but platform-specific and can miss events under high I/O load. Periodic polling catches everything but is slow for large directories and wastes CPU/battery. Dropbox uses events as primary, polling as fallback."
            }
        ],
        "common_mistakes": [
            "Uploading the entire file on every change instead of only changed blocks — wastes bandwidth for large files",
            "Using timestamp-based conflict detection instead of version vectors — clock skew causes false conflicts or missed conflicts",
            "Not handling the resume case: if upload is interrupted, client must be able to resume from the last successful block",
            "Ignoring content-addressable storage — storing the same block N times for N users who have the same file",
            "Polling the filesystem for changes instead of using native filesystem event APIs — drains battery on laptops",
            "Treating file metadata (name, permissions) and content as a single atomic unit — they can change independently",
            "No selective sync — forcing all folders to sync to all devices, which overwhelms devices with limited storage"
        ],
        "solution_outline": {
            "entities": [
                "File: {file_id, workspace_id, path, current_version, is_deleted, created_at, modified_at}",
                "FileVersion: {version_id, file_id, block_list: [{block_hash, offset, size}], author_id, timestamp, version_vector}",
                "Block: {block_hash (SHA-256), size, ref_count, storage_url}",
                "Workspace: {workspace_id, owner_id, members, quota_bytes, used_bytes}",
                "SyncCursor: {device_id, workspace_id, last_sync_journal_id}"
            ],
            "api_sketch": [
                "POST /api/v1/files/check-blocks  {block_hashes: [string]} -> {needed: [string], existing: [string]}",
                "PUT /api/v1/blocks/{hash}  (binary block data) -> 200",
                "POST /api/v1/files/commit  {path, block_list, parent_version} -> {file_id, version_id} or {conflict: true, conflicting_version}",
                "GET /api/v1/sync/changes?cursor=X -> {changes: [{path, version, is_deleted}], new_cursor}",
                "GET /api/v1/files/{id}/download -> redirect to pre-signed block URLs",
                "GET /api/v1/files/{id}/versions -> [{version_id, timestamp, author, size}]"
            ],
            "components": [
                "Sync Client: filesystem watcher, block splitter/hasher, upload/download manager, local SQLite state DB",
                "Block Store: content-addressable object storage (S3/GCS), reference counting for garbage collection",
                "Metadata Service: file tree, versions, permissions — sharded by workspace_id",
                "Sync Journal: ordered log of changes per workspace, used for incremental sync via cursors",
                "Conflict Resolver: detects concurrent edits via version vectors, creates conflicted copies",
                "Notification Service: long-poll or WebSocket to notify clients of remote changes",
                "Sharing Service: manages workspace members, shared links, permission inheritance"
            ],
            "data_flow": "Upload: Client detects file change via FSEvents -> split file into blocks -> hash each block -> POST /check-blocks to find which are new -> upload only new blocks -> POST /commit with block list and parent version -> server checks for conflicts -> if no conflict: update metadata, append to sync journal, notify other devices -> if conflict: return conflict, client creates conflicted copy. Download: Client polls /sync/changes (or receives push notification) -> gets list of changed files -> for each file: download block list -> check which blocks are already local -> download missing blocks -> assemble file -> update local state DB."
        },
        "teaching_notes": {
            "opening_question": "You save a file on your laptop and it appears on your phone 5 seconds later. What happened in those 5 seconds?",
            "key_insight": "Dropbox is a distributed state synchronization system disguised as a simple file sharing product. The hard problem is not storage — it is synchronizing state across devices with concurrent modifications, unreliable networks, and different filesystem semantics.",
            "scaffolding_hints": [
                "If they upload whole files, ask: 'You change 1 byte in a 10GB file. How much data gets uploaded?'",
                "If they use timestamps for versioning, ask: 'What if the laptop's clock is 5 minutes behind? How do you know which edit came first?'",
                "If they skip conflict detection, ask: 'Two people edit the same file on different laptops with no internet. What happens when both come online?'",
                "If they poll for changes, ask: 'How often do you scan a folder with 500,000 files, and how long does each scan take?'"
            ],
            "when_to_push": "Push when the candidate treats file sync as simple upload/download without addressing deduplication, delta sync, or conflict resolution. These are the core engineering challenges.",
            "when_to_help": "Help if they are unfamiliar with content-addressable storage — explain the concept: 'the file's hash IS its address' and show how this enables deduplication naturally."
        }
    },

    # -----------------------------------------------------------------------
    # 12. KEY-VALUE STORE
    # -----------------------------------------------------------------------
    "design-key-value-store": {
        "level_expectations": {
            "mid": "Should describe a hash table distributed across nodes using consistent hashing, basic replication for fault tolerance, and simple get/put operations with eventual consistency.",
            "senior": "Must implement consistent hashing with virtual nodes, design quorum-based reads/writes (R + W > N), handle node failure detection with gossip protocol, and discuss read repair and anti-entropy mechanisms.",
            "staff": "Expected to design a Dynamo-style system with tunable consistency, implement Merkle trees for anti-entropy, discuss vector clocks for conflict detection, handle hinted handoff for transient failures, and reason about the CAP theorem trade-offs for different configurations."
        },
        "edge_cases": [
            "Node fails during a write — data is on 1 of 3 replicas. Client reads from the 2 replicas without the write — stale read",
            "Network partition splits the cluster into two halves — both halves accept writes to the same key, creating divergent values",
            "Hot key: one key receives 100K reads/second — the node responsible for that key is overwhelmed",
            "Clock skew between nodes causes last-write-wins to pick the wrong winner",
            "Node rejoins after being partitioned for 1 hour — has stale data for thousands of keys that were updated during partition",
            "Ring rebalancing when adding a new node — data migration must happen without downtime or consistency violations",
            "Key with very large value (100MB) — exceeds typical value size limits, causes replication lag"
        ],
        "follow_ups": [
            "How would you implement range queries on top of this key-value store?",
            "Design a TTL (time-to-live) feature for automatic key expiration.",
            "How would you add multi-datacenter replication for disaster recovery?",
            "Design the monitoring and alerting system for the key-value store cluster.",
            "How would you implement transactions (multi-key atomic operations) on top of this eventually consistent store?"
        ],
        "deep_dives": [
            {
                "topic": "Consistent Hashing with Virtual Nodes",
                "why_important": "Consistent hashing determines which node stores which keys. Without virtual nodes, adding/removing nodes causes massive data redistribution. Virtual nodes ensure even distribution and smooth rebalancing.",
                "key_points": [
                    "Hash ring: keys and nodes are hashed to positions on a ring (0 to 2^128). Key is stored on the first node clockwise from its position",
                    "Problem with basic consistent hashing: uneven distribution when nodes have different capacities, and removing a node dumps all its keys onto one neighbor",
                    "Virtual nodes: each physical node claims 100-200 positions on the ring. Distributes load more evenly, and removing a node spreads its keys across many neighbors",
                    "Replication: key is stored on N consecutive distinct physical nodes on the ring (typically N=3)"
                ],
                "trade_offs": "More virtual nodes per physical node gives more even distribution but increases metadata size and routing table lookups. Too few virtual nodes causes hot spots. The sweet spot is 100-200 virtual nodes per physical node."
            },
            {
                "topic": "Quorum Reads/Writes and Tunable Consistency",
                "why_important": "The quorum protocol (R + W > N) is how the system provides tunable consistency — from strong consistency to eventual consistency — without changing the architecture. It is the central mechanism that lets users trade latency for consistency.",
                "key_points": [
                    "N = number of replicas (typically 3). W = number of replicas that must acknowledge a write. R = number of replicas that must respond to a read",
                    "Strong consistency: R + W > N (e.g., R=2, W=2, N=3). At least one replica in every read overlaps with every write",
                    "High availability writes: W=1, R=3 — write succeeds if any one replica is up, read must contact all replicas",
                    "High availability reads: W=3, R=1 — writes are slow but reads are fast and always consistent",
                    "Eventual consistency: R=1, W=1 — fastest but may read stale data"
                ],
                "trade_offs": "R+W>N guarantees reading the latest write but increases latency (must wait for slower replicas). R=1,W=1 is fastest but sacrifices consistency. The key insight: there is no 'best' setting — it depends on the use case. Shopping cart: eventual consistency is fine. Bank balance: strong consistency is required."
            },
            {
                "topic": "Failure Detection: Gossip Protocol",
                "why_important": "In a distributed system, nodes fail silently. The gossip protocol detects failures without a single point of failure (no central monitor). It is the foundation for knowing which nodes are alive and where data should be routed.",
                "key_points": [
                    "Each node periodically (every 1s) picks a random node and exchanges membership lists",
                    "Membership list: {node_id -> (heartbeat_counter, timestamp_last_incremented)}",
                    "If a node's heartbeat has not incremented for T seconds, mark it as suspected. After 2T seconds with no update, mark as failed",
                    "Phi-accrual failure detector (Cassandra): instead of binary alive/dead, compute a suspicion level that adapts to network conditions",
                    "When a node is detected as failed: its key ranges are temporarily served by neighboring nodes (hinted handoff)"
                ],
                "trade_offs": "Faster detection (shorter T) means quicker failover but more false positives (marking slow nodes as dead). Slower detection is more accurate but delays recovery. Phi-accrual detector adapts automatically but is more complex to implement."
            },
            {
                "topic": "Anti-Entropy: Merkle Trees and Read Repair",
                "why_important": "Replicas drift out of sync due to failed writes, network partitions, and hinted handoffs. Anti-entropy mechanisms detect and repair inconsistencies in the background, ensuring eventual convergence.",
                "key_points": [
                    "Read repair: on every read, compare values from R replicas. If they disagree, write the latest value back to stale replicas. 'Piggybacks' repair on normal read traffic",
                    "Merkle trees: each node maintains a hash tree over its key-value pairs. To sync two replicas: compare root hashes -> if different, recurse into children -> identify the specific keys that differ -> transfer only those keys",
                    "Merkle tree comparison: O(log N) comparisons to find differing keys, vs O(N) for full scan",
                    "Active anti-entropy: background process periodically compares Merkle trees between replicas and repairs differences"
                ],
                "trade_offs": "Read repair is free (happens during normal reads) but only fixes keys that are actually read — cold keys stay inconsistent. Merkle tree repair fixes everything but consumes background bandwidth and CPU. Use both: read repair for hot keys, Merkle trees for cold keys."
            }
        ],
        "common_mistakes": [
            "Using a single hash function without virtual nodes — leads to severely uneven key distribution",
            "Claiming the system is 'consistent' without specifying quorum settings or what 'consistent' means (linearizable? eventual?)",
            "Not handling the case where a write succeeds on W replicas but the coordinator crashes before returning to the client — client retries, causing duplicate writes without idempotency",
            "Using wall-clock timestamps for last-write-wins without acknowledging clock skew — leads to silent data loss",
            "Forgetting hinted handoff: when a replica node is down, writes must be temporarily stored on another node and forwarded when the failed node recovers",
            "Not discussing how to handle hot keys — consistent hashing does not help when one key gets 100K reads/second",
            "Treating partition tolerance as optional — network partitions WILL happen in any distributed system"
        ],
        "solution_outline": {
            "entities": [
                "KeyValuePair: {key, value, version_vector, timestamp}",
                "Node: {node_id, ip_address, virtual_node_tokens: [int], status (alive/suspected/dead), datacenter}",
                "HintedHandoff: {target_node_id, key, value, version_vector, created_at}",
                "MerkleTree: {node_id, key_range, root_hash, tree_structure}"
            ],
            "api_sketch": [
                "PUT /kv/{key}  {value, consistency: 'one'|'quorum'|'all'} -> {version}",
                "GET /kv/{key}?consistency=quorum -> {value, version}",
                "DELETE /kv/{key} -> {version} (tombstone, not physical delete)",
                "Internal: REPLICATE(key, value, version) -> sent to replica nodes",
                "Internal: GOSSIP(membership_list) -> exchanged between nodes periodically",
                "Admin: GET /cluster/status -> {nodes: [{id, status, key_ranges, load}]}"
            ],
            "components": [
                "Client Library: handles request routing (knows the hash ring), retry logic, and quorum coordination",
                "Storage Engine: per-node key-value storage (LSM tree or B-tree backed), handles local reads/writes",
                "Partitioner: consistent hash ring with virtual nodes, determines key-to-node mapping",
                "Replication Manager: coordinates writes to N replicas, waits for W acknowledgments",
                "Gossip Service: failure detection, membership management, cluster state propagation",
                "Anti-Entropy Service: Merkle tree comparison and background repair between replicas",
                "Hinted Handoff Queue: stores writes destined for failed nodes, replays when they recover",
                "Read Repair: compares values during reads, patches stale replicas inline"
            ],
            "data_flow": "Write: Client hashes key -> determine coordinator node from ring -> coordinator sends write to N replica nodes in parallel -> wait for W acknowledgments -> return success. If a replica is down: store in hinted handoff queue on a temporary node. Read: Client hashes key -> coordinator sends read to N replicas -> wait for R responses -> compare values (version vectors) -> if conflict: return all versions for client resolution (or apply LWW) -> if stale replica detected: trigger read repair. Background: Gossip protocol detects node failures -> reassign key ranges -> Anti-entropy Merkle tree sync runs every 10 minutes between replicas."
        },
        "teaching_notes": {
            "opening_question": "How would you design a key-value store that never goes down, even when servers crash? What do you have to give up to achieve that?",
            "key_insight": "A distributed key-value store is a concrete exploration of the CAP theorem. Every design decision is a trade-off between consistency, availability, and partition tolerance. The candidate should understand that there is no universally 'correct' design — the right choice depends on the application's requirements.",
            "scaffolding_hints": [
                "If they use a single server, ask: 'What happens when that server crashes? Is all data lost?'",
                "If they replicate but do not discuss consistency, ask: 'If you write to replica A and read from replica B before it syncs, what value do you get?'",
                "If they skip failure detection, ask: 'How does the system know that a node has crashed and should stop receiving traffic?'",
                "If they claim strong consistency and high availability, ask: 'What happens during a network partition? Can you have both?'"
            ],
            "when_to_push": "Push when the candidate claims their system is both consistent and highly available without discussing what happens during a network partition. This is the CAP theorem — they must make a choice.",
            "when_to_help": "Help if they are unfamiliar with consistent hashing — draw the ring, show how keys map to nodes, and demonstrate what happens when a node is added or removed."
        }
    },

    # -----------------------------------------------------------------------
    # 13. TICKETMASTER
    # -----------------------------------------------------------------------
    "design-ticketmaster-booking-system": {
        "level_expectations": {
            "mid": "Should identify the seat reservation problem, propose a database with row-level locking for seat selection, and handle basic payment flow. Should mention the high-traffic nature of ticket sales.",
            "senior": "Must design distributed locking for seat reservation (optimistic or pessimistic), implement a virtual queue for flash sales, handle payment timeout and seat release (temporary hold pattern), and discuss inventory consistency across concurrent buyers.",
            "staff": "Expected to design the full system for flash-sale scale (millions of users hitting the system in seconds), implement a fair virtual queue with position tracking, design the seat map with real-time availability updates, handle partial failures in the payment flow, and plan CDN strategy for absorbing traffic spikes."
        },
        "edge_cases": [
            "Two users select the same seat at the same time — only one should succeed, the other must get a clear error",
            "User adds seat to cart but never completes payment — seat is held indefinitely without a timeout",
            "Payment provider times out — did the charge go through? Seat is in limbo between held and released",
            "User opens two browser tabs and tries to buy different seats in each — inventory must be consistent across sessions",
            "Scalper bot sends 10,000 requests in 1 second to grab all best seats — must be detected and blocked",
            "Event is cancelled after 50,000 tickets are sold — mass refund processing",
            "Venue changes seating layout after some tickets are sold — must reconcile sold seats with new layout",
            "Flash sale for 10,000 seats with 500,000 concurrent users — system must remain responsive"
        ],
        "follow_ups": [
            "How would you design the virtual queue system that shows users their position and estimated wait time?",
            "Design the dynamic pricing system where ticket prices change based on demand.",
            "How would you implement a waitlist that automatically offers tickets when someone cancels?",
            "Design the anti-bot system to prevent automated scalping.",
            "How would you handle a venue with general admission (no assigned seats) differently from assigned seating?",
            "Design the ticket transfer and resale marketplace."
        ],
        "deep_dives": [
            {
                "topic": "Seat Reservation with Distributed Locks",
                "why_important": "The core challenge of ticket booking is ensuring that exactly one buyer can purchase a specific seat. Without proper locking, double-booking occurs — which is a catastrophic failure (two people show up for the same seat).",
                "key_points": [
                    "Pessimistic locking: SELECT ... FOR UPDATE on the seat row. Simple and correct but limits concurrency — 10,000 users contending for the same row creates a bottleneck",
                    "Optimistic locking: read seat version, attempt UPDATE with WHERE version=X. If another buyer got it first, the update affects 0 rows — retry with a different seat",
                    "Temporary hold: when user selects a seat, mark it as 'held' with a TTL (10 minutes). If payment is not completed within TTL, release the seat automatically",
                    "Redis-based distributed lock: SETNX with TTL for the seat key. Faster than DB locks for high-contention scenarios"
                ],
                "trade_offs": "Pessimistic locking is safest but kills performance under high contention. Optimistic locking scales better but causes many retries during flash sales. Temporary hold with TTL is the practical approach — it balances consistency with UX (user has time to enter payment info)."
            },
            {
                "topic": "Virtual Queue for Flash Sales",
                "why_important": "When 500K users try to buy 10K tickets simultaneously, hitting the booking system directly would crash it. A virtual queue absorbs the spike, gives users a fair position, and meters traffic to what the backend can handle.",
                "key_points": [
                    "Queue entry: user joins queue at sale start time, receives a queue position (based on arrival time + randomization to prevent bot advantage)",
                    "Token-based admission: as seats become available (checkout timeouts, releases), next users in queue receive a short-lived purchase token",
                    "Rate limiting: admit users to the booking flow at a controlled rate (e.g., 100 users/second) that the backend can handle",
                    "Position updates: real-time WebSocket updates showing queue position and estimated wait time",
                    "Anti-bot: CAPTCHA at queue entry, device fingerprinting, rate limiting per IP"
                ],
                "trade_offs": "Virtual queue adds latency (users wait minutes instead of racing) but prevents system crashes and ensures fairness. Without a queue, the fastest network connection wins — which favors bots. Trade-off: user experience (waiting is frustrating) vs. system stability."
            },
            {
                "topic": "Payment Timeout and Seat Release",
                "why_important": "The gap between seat selection and payment completion is dangerous — seats are held (unavailable to others) but money has not been collected. If holds are not managed carefully, inventory gets stuck and seats go unsold.",
                "key_points": [
                    "Temporary hold: seat status transitions AVAILABLE -> HELD (with hold_expires_at = now + 10 min) -> SOLD (on payment) or AVAILABLE (on timeout)",
                    "Hold cleanup: background job scans for expired holds every 30 seconds, releases them back to inventory",
                    "Payment failure handling: if payment charge fails, immediately release the hold and notify the user",
                    "Payment timeout: if payment provider does not respond within 30 seconds, mark as 'pending verification', do NOT release seat yet — query payment provider for status",
                    "Idempotent payment: use a unique order_id as idempotency key to prevent double-charging on retry"
                ],
                "trade_offs": "Short hold time (5 min) maximizes inventory availability but pressures users. Long hold time (30 min) is user-friendly but locks inventory from other buyers. 10-15 minutes is the industry standard. For high-demand events, shorter holds are justified."
            }
        ],
        "common_mistakes": [
            "Not implementing a temporary hold — seats go from available to sold with no intermediate state, causing double-booking during payment processing",
            "Using application-level locks instead of database/distributed locks — multiple application instances can bypass the lock",
            "No timeout on seat holds — abandoned carts lock up inventory forever",
            "Letting all users hit the booking system simultaneously during flash sales instead of using a queue",
            "Not handling payment provider timeouts — the system does not know if the charge went through, leading to either double-charge or lost sale",
            "Ignoring bot detection — scalper bots grab all tickets before real users can load the page",
            "Designing the seat map as a single shared state object that all users poll — creates a hot spot"
        ],
        "solution_outline": {
            "entities": [
                "Event: {event_id, venue_id, name, date, total_seats, available_seats, sale_start_at, status (upcoming/on_sale/sold_out)}",
                "Seat: {seat_id, event_id, section, row, number, price_tier, status (available/held/sold), held_by_order, hold_expires_at}",
                "Order: {order_id, user_id, event_id, seats: [seat_id], status (pending/paid/cancelled/refunded), total_amount, created_at, payment_deadline}",
                "QueueTicket: {queue_id, user_id, event_id, position, joined_at, purchase_token, token_expires_at}",
                "Payment: {payment_id, order_id, amount, provider, status (pending/completed/failed/refunded), idempotency_key}"
            ],
            "api_sketch": [
                "POST /api/v1/events/{id}/queue/join -> {queue_position, estimated_wait}",
                "WebSocket /ws/queue/{queue_id} -> real-time position updates, purchase_token when admitted",
                "POST /api/v1/events/{id}/hold-seats  {seat_ids, purchase_token} -> {order_id, hold_expires_at}",
                "POST /api/v1/orders/{id}/pay  {payment_method} -> {status, receipt}",
                "DELETE /api/v1/orders/{id}  -> release held seats",
                "GET /api/v1/events/{id}/seats?section=A -> {seats: [{id, row, number, status, price}]}"
            ],
            "components": [
                "Event Catalog Service: event listing, search, venue/seating configuration",
                "Queue Service: virtual queue management, position tracking, token issuance, anti-bot (CAPTCHA, fingerprinting)",
                "Inventory Service: seat availability, hold/release with TTL, real-time seat map updates",
                "Booking Service: orchestrates seat hold -> payment -> confirmation flow",
                "Payment Service: integrates with Stripe/PayPal, idempotent charges, handles timeouts and retries",
                "Hold Cleanup Worker: background job that releases expired holds every 30s",
                "CDN / Static Edge: serves event pages, seat maps (static assets) from CDN to absorb traffic spikes",
                "Notification Service: confirmation emails, e-tickets, event reminders"
            ],
            "data_flow": "Flash Sale: Sale opens -> 500K users -> Queue Service assigns positions -> admits users at controlled rate (100/s) -> admitted user receives purchase_token -> user selects seats -> Booking Service: verify token, atomically hold seats (optimistic lock on seat rows), set hold_expires_at -> user enters payment -> Payment Service charges with idempotency key -> on success: update seat status to SOLD, send confirmation -> on timeout: query payment provider, decide hold/release -> Hold Cleanup Worker: every 30s, find WHERE hold_expires_at < now AND status = HELD, set status = AVAILABLE."
        },
        "teaching_notes": {
            "opening_question": "Taylor Swift announces a concert with 50,000 seats. 2 million fans try to buy tickets the moment they go on sale. What breaks first?",
            "key_insight": "Ticketmaster is an inventory management problem under extreme contention. The core challenge is not building a web app — it is ensuring exactly-once seat assignment when millions of users are racing for limited inventory, while handling the inevitable failures in payment processing.",
            "scaffolding_hints": [
                "If they do not address concurrency, ask: 'What happens when two users click Buy on the same seat at the same millisecond?'",
                "If they skip the hold pattern, ask: 'User selects a seat and starts entering credit card info. What is the seat's status during those 2 minutes?'",
                "If they let all users hit the backend, ask: 'Can your system handle 2 million simultaneous HTTP requests?'",
                "If they forget payment failures, ask: 'The payment provider times out. Did the charge go through? What happens to the seat?'"
            ],
            "when_to_push": "Push when the candidate does not address the race condition between seat selection and payment completion, or when they treat the traffic spike as just a 'scaling problem' without a queue.",
            "when_to_help": "Help if they are unfamiliar with optimistic vs pessimistic locking — explain both patterns with a concrete example (two users, one seat, one database row) and let them choose."
        }
    },

    # -----------------------------------------------------------------------
    # 14. PAYMENT SYSTEM
    # -----------------------------------------------------------------------
    "design-payment-system": {
        "level_expectations": {
            "mid": "Should describe the basic payment flow (user, merchant, payment processor), mention the need for a transaction record, and discuss basic error handling for failed payments.",
            "senior": "Must design idempotent payment processing with idempotency keys, implement double-entry bookkeeping for the ledger, discuss retry logic for payment provider failures, and handle webhook notifications for async payment status updates.",
            "staff": "Expected to design the full payment platform with PCI compliance (tokenization, vault), implement reconciliation between the ledger and external payment providers, design for multi-currency with exchange rates, handle regulatory requirements (KYC/AML), and discuss exactly-once processing guarantees."
        },
        "edge_cases": [
            "Network timeout after sending charge request to payment provider — did it go through? Must query status before retrying",
            "Double-click on Pay button sends two identical requests — without idempotency key, user is charged twice",
            "Payment succeeds but the response is lost due to network failure — system shows 'payment failed' but money was taken",
            "Refund requested for a payment that is still in 'pending' state — cannot refund what has not settled",
            "Currency conversion: user pays in EUR, merchant receives USD — which exchange rate: at order time or settlement time?",
            "Partial refund on a discounted order — how to allocate the refund across original line items",
            "Payment provider's webhook arrives before the synchronous response — race condition in status update",
            "Card declined but user's bank shows a temporary hold — hold drops after 7 days but user is confused"
        ],
        "follow_ups": [
            "How would you implement a wallet/balance system where users can top up and pay from their balance?",
            "Design the settlement and payout system for merchants — how do daily/weekly payouts work?",
            "How would you add support for subscriptions with automatic recurring billing?",
            "Design the fraud detection system that blocks suspicious transactions in real-time.",
            "How would you handle multi-party payments (e.g., marketplace where platform takes a commission)?",
            "Design the dispute/chargeback handling flow."
        ],
        "deep_dives": [
            {
                "topic": "Idempotency Keys for Exactly-Once Payment Processing",
                "why_important": "Charging a customer twice is one of the worst bugs a payment system can have. Idempotency keys ensure that retrying a failed payment request does not result in a duplicate charge, even across network failures and timeouts.",
                "key_points": [
                    "Client generates a unique idempotency key (UUID) for each payment intent and sends it with every request (including retries)",
                    "Server stores: {idempotency_key -> (status, response)}. On receiving a request with a known key, return the stored response without re-executing",
                    "Implementation: before processing, check if idempotency_key exists in DB. If yes and completed: return stored response. If yes and in-progress: return 409 Conflict. If no: insert key with 'in-progress', process payment, update with result",
                    "TTL on idempotency records: keep for 24-48 hours, then clean up (retries after 48 hours are unlikely)",
                    "The idempotency key must be scoped to the payment attempt, not the order — a retry is the same key, a new payment attempt on the same order is a different key"
                ],
                "trade_offs": "Idempotency adds a DB lookup to every payment request (latency). Using a fast store (Redis) for the key-result mapping minimizes impact. The alternative — no idempotency — risks double charges, which is far worse."
            },
            {
                "topic": "Double-Entry Ledger",
                "why_important": "A double-entry ledger is the accounting foundation of any financial system. It ensures that money is never created or destroyed — every credit has a corresponding debit. Without it, reconciliation is impossible and financial audits fail.",
                "key_points": [
                    "Every transaction creates two entries: debit from one account, credit to another. The sum of all debits always equals the sum of all credits",
                    "Account types: user balance, merchant balance, platform revenue, payment provider clearing, refund reserve",
                    "Example: user pays $100 -> debit user_payment_account $100, credit merchant_receivable_account $100. Platform fee $5 -> debit merchant_receivable_account $5, credit platform_revenue_account $5",
                    "Immutable entries: never update or delete a ledger entry. Corrections are new entries that reverse the original (contra entries)",
                    "Audit trail: every entry has timestamp, actor, reference (order_id, payment_id), and reason"
                ],
                "trade_offs": "Double-entry is more complex than a simple balance field (balance += amount) but prevents a whole class of bugs where money appears or disappears. It is a regulatory requirement for any company handling money."
            },
            {
                "topic": "Reconciliation with External Payment Providers",
                "why_important": "The payment system's ledger and the payment provider's records can diverge due to network failures, timeout edge cases, and delayed webhooks. Reconciliation detects and resolves these discrepancies before they become customer complaints or financial losses.",
                "key_points": [
                    "Daily batch reconciliation: download settlement report from Stripe/PayPal, compare every transaction with internal ledger",
                    "Discrepancy types: transaction in our ledger but not in provider (we think it succeeded, but it did not), transaction in provider but not in our ledger (charge went through but we did not record it), amount mismatch",
                    "Resolution: for missing charges: verify with provider API, update ledger or refund. For unrecorded charges: create a ledger entry post-hoc. For amount mismatches: investigate and create adjustment entries",
                    "Real-time reconciliation: compare webhook events with internal state as they arrive, flag discrepancies immediately"
                ],
                "trade_offs": "Daily batch reconciliation catches everything but discrepancies are discovered up to 24 hours late. Real-time reconciliation detects issues immediately but adds complexity and may produce false alarms from race conditions (webhook arrives before sync response)."
            },
            {
                "topic": "PCI Compliance and Card Data Handling",
                "why_important": "Storing raw credit card numbers exposes the company to massive liability (fines, lawsuits, brand damage). PCI DSS compliance determines what data you can store, how you handle it, and what infrastructure requirements you must meet.",
                "key_points": [
                    "Tokenization: never store raw card numbers. Use a PCI-compliant vault (Stripe, Braintree) that returns a token representing the card",
                    "Token flow: client sends card details directly to payment provider's JS SDK (never touches your server), receives a token, sends token to your server, your server uses token for charges",
                    "PCI scope reduction: by never handling raw card data, your application is in PCI SAQ-A (simplest compliance level) instead of SAQ-D (most burdensome)",
                    "Sensitive data handling: even tokenized, store minimal card info (last 4 digits, expiry, brand) for display purposes only"
                ],
                "trade_offs": "Using a third-party vault (Stripe) means you are dependent on their availability and pricing. Building your own vault gives more control but requires PCI Level 1 compliance (annual on-site audit, network segmentation, encryption at rest and in transit) — extremely expensive and complex."
            }
        ],
        "common_mistakes": [
            "Not implementing idempotency keys — double-clicks or network retries cause double charges",
            "Using a simple balance column (balance += amount) instead of a double-entry ledger — makes reconciliation and auditing impossible",
            "Storing credit card numbers in the application database — PCI violation, massive security risk",
            "Treating payment provider responses as instant and reliable — timeouts, delayed webhooks, and inconsistent states are common",
            "Not implementing reconciliation — the internal ledger silently diverges from the payment provider over time",
            "Synchronous payment processing: blocking the user's request for 30+ seconds while the payment provider processes",
            "No idempotent refunds — processing the same refund request twice returns double the money"
        ],
        "solution_outline": {
            "entities": [
                "PaymentIntent: {payment_id, order_id, user_id, amount, currency, status (created/processing/succeeded/failed/refunded), idempotency_key, created_at}",
                "LedgerEntry: {entry_id, payment_id, account_id, type (debit/credit), amount, currency, created_at, description}",
                "Account: {account_id, type (user/merchant/platform/clearing), balance (computed from ledger entries), currency}",
                "PaymentMethod: {method_id, user_id, type (card/bank), provider_token, last_four, brand, expires_at}",
                "Refund: {refund_id, payment_id, amount, reason, status, idempotency_key}"
            ],
            "api_sketch": [
                "POST /api/v1/payments  {order_id, amount, currency, payment_method_id, idempotency_key} -> {payment_id, status}",
                "GET /api/v1/payments/{id} -> {payment details, ledger entries}",
                "POST /api/v1/payments/{id}/refund  {amount, reason, idempotency_key} -> {refund_id, status}",
                "POST /api/v1/payment-methods  {provider_token, type} -> {method_id}",
                "POST /webhooks/stripe -> handle async payment status updates",
                "GET /api/v1/accounts/{id}/balance -> {balance, currency, pending_amount}"
            ],
            "components": [
                "Payment Service: orchestrates payment flow, idempotency enforcement, status management",
                "Ledger Service: double-entry bookkeeping, immutable entries, balance computation",
                "Payment Provider Adapter: abstracts Stripe/PayPal/Adyen behind a common interface",
                "Webhook Handler: receives and processes async events from payment providers, updates payment status",
                "Reconciliation Service: daily batch comparison of internal ledger vs provider settlement reports",
                "Tokenization Proxy: PCI-scoped service that handles payment method tokenization (or delegates to provider SDK)",
                "Notification Service: sends payment confirmation/failure emails and push notifications",
                "Fraud Detection: rule-based and ML-based transaction scoring, blocks suspicious payments pre-authorization"
            ],
            "data_flow": "Payment: Client -> create PaymentIntent with idempotency_key -> check idempotency store -> if new: charge via Payment Provider Adapter (Stripe API call) -> on success: create LedgerEntry pair (debit user, credit merchant) -> update PaymentIntent status -> notify user. Provider Timeout: if Stripe does not respond in 30s -> mark as 'pending_verification' -> background job queries Stripe API for status -> update accordingly. Webhook: Stripe sends async event -> Webhook Handler validates signature -> updates PaymentIntent status -> triggers reconciliation check. Reconciliation: daily cron job downloads Stripe settlement CSV -> compares each transaction with LedgerEntry table -> flags discrepancies -> ops team resolves."
        },
        "teaching_notes": {
            "opening_question": "You click 'Pay $50' and your screen shows a loading spinner. The spinner times out. Were you charged? How does the system handle this?",
            "key_insight": "A payment system is a distributed transaction problem where the two parties (your system and the payment provider) can disagree about the outcome. Every design decision must account for the fact that network calls can fail, succeed silently, or return ambiguous results — and the consequence of getting it wrong is real money.",
            "scaffolding_hints": [
                "If they treat payment as a simple API call, ask: 'What happens if the Stripe API call times out — were they charged or not?'",
                "If they skip idempotency, ask: 'User's browser retries the payment request because it thought the first one failed. What happens?'",
                "If they use a simple balance field, ask: 'How do you prove to an auditor that every dollar in and every dollar out is accounted for?'",
                "If they store card numbers, ask: 'What are the legal and security implications of storing raw credit card data?'"
            ],
            "when_to_push": "Push when the candidate treats payment as a happy-path problem without addressing timeouts, retries, and ambiguous states. Also push if they skip the ledger — it is the foundation of financial system correctness.",
            "when_to_help": "Help if they are unfamiliar with idempotency keys — explain the concept with a concrete example: 'same key, same result, no matter how many times you call it' and let them integrate it into their design."
        }
    },

    # -----------------------------------------------------------------------
    # 15. DISTRIBUTED CACHE
    # -----------------------------------------------------------------------
    "design-distributed-cache": {
        "level_expectations": {
            "mid": "Should describe a hash-based partitioning scheme for distributing keys across cache nodes, explain LRU eviction, and discuss cache-aside pattern for database caching.",
            "senior": "Must compare caching strategies (cache-aside vs write-through vs write-back), design for cache stampede prevention, discuss consistent hashing for node management, and handle cache invalidation for data consistency.",
            "staff": "Expected to design a production-grade distributed cache with hot key handling (local caching, key splitting), implement probabilistic early expiry to prevent stampede, discuss cache coherence protocols in multi-datacenter setups, and design monitoring/alerting for cache hit rates and latency percentiles."
        },
        "edge_cases": [
            "Cache stampede: cached item expires and 1000 concurrent requests hit the database simultaneously to repopulate it",
            "Hot key: one key (e.g., trending post) receives 100K reads/second — single cache node becomes bottleneck",
            "Cache node dies: all keys on that node become misses, causing a flood of database queries (cold start problem)",
            "Stale cache: database was updated but cache still has old value — user sees inconsistent data",
            "Large value: cached object is 50MB, exceeds typical cache item size limit and causes eviction thrashing",
            "Thundering herd on cache warm-up: new cache node joins the cluster and has no data — all requests to its key range miss",
            "Serialization incompatibility: application deploys a new version that changes the cached object's schema — old cached objects cause deserialization errors"
        ],
        "follow_ups": [
            "How would you implement cache warming — pre-populating the cache before traffic arrives?",
            "Design a cache that works across multiple datacenters with acceptable consistency.",
            "How would you add TTL-based expiry that does not cause stampedes at expiry time?",
            "Design the monitoring dashboard for a distributed cache — what metrics matter most?",
            "How would you implement a write-back cache with durability guarantees?",
            "Design a cache that supports range queries, not just point lookups."
        ],
        "deep_dives": [
            {
                "topic": "Eviction Policies: LRU vs LFU vs TTL",
                "why_important": "Cache memory is finite. The eviction policy determines which items are removed when the cache is full — a poor policy evicts hot items and keeps cold ones, destroying the cache hit rate.",
                "key_points": [
                    "LRU (Least Recently Used): evict the item accessed longest ago. Simple, works well for temporal locality. O(1) with hash map + doubly-linked list",
                    "LFU (Least Frequently Used): evict the item accessed fewest times. Better for stable popularity patterns, but slow to adapt to changing access patterns (old popular items cling)",
                    "TTL (Time-To-Live): each item has an expiry time, evict when expired. Not an eviction policy per se — used alongside LRU/LFU for correctness (stale data removal)",
                    "W-TinyLFU (used by Caffeine): admission filter + LRU window — combines the benefits of LFU (frequency awareness) with LRU (recency adaptation). Best general-purpose policy",
                    "Random eviction: surprisingly effective and simplest to implement — within 10-15% of optimal in many workloads"
                ],
                "trade_offs": "LRU is the default choice — simple and effective for most workloads. LFU is better when access frequency is more important than recency (e.g., CDN edge caches). W-TinyLFU is best overall but more complex to implement. The choice matters most when cache is small relative to working set."
            },
            {
                "topic": "Caching Strategies: Cache-Aside vs Write-Through vs Write-Back",
                "why_important": "The caching strategy determines the consistency model, write latency, and failure behavior. Choosing the wrong strategy for the workload causes either stale reads or unnecessary write latency.",
                "key_points": [
                    "Cache-Aside (Lazy Loading): application reads from cache first. On miss, read from DB, populate cache. On write, write to DB, invalidate cache. Most common, simplest",
                    "Write-Through: every write goes to both cache and DB synchronously. Cache is always consistent, but writes are slower (two writes per operation)",
                    "Write-Back (Write-Behind): write to cache only, asynchronously flush to DB in batches. Fastest writes, but data loss risk if cache crashes before flush",
                    "Read-Through: cache itself handles DB reads on miss (cache is 'smart'). Simplifies application code but couples cache to DB"
                ],
                "trade_offs": "Cache-aside is most flexible but can serve stale data between DB write and cache invalidation. Write-through eliminates staleness but doubles write latency. Write-back is fastest for writes but risks data loss. Most systems use cache-aside for reads and direct DB writes with cache invalidation."
            },
            {
                "topic": "Cache Stampede Prevention",
                "why_important": "When a popular cached item expires, thousands of concurrent requests miss the cache simultaneously and all hit the database. This can overload the database and cascade into a system-wide outage. It is the most common distributed cache failure mode.",
                "key_points": [
                    "Mutex/lock-based: on cache miss, only one request acquires a lock and rebuilds the cache. Others wait or get stale value. Prevents parallel DB queries",
                    "Probabilistic early expiry (XFetch): each request has a small probability of refreshing the value BEFORE it expires. As more requests arrive near expiry, probability of at least one refresh approaches 1",
                    "Background refresh: a background thread refreshes popular items before they expire. No miss ever reaches the application",
                    "Stale-while-revalidate: serve the stale value while asynchronously refreshing from DB. User sees slightly old data but never sees a cache miss"
                ],
                "trade_offs": "Mutex is simplest and most effective but adds latency for waiting requests. Probabilistic early expiry is elegant (no coordination needed) but may waste a few extra DB queries. Background refresh is best for predictable hot keys but wastes resources refreshing keys that might not be requested."
            },
            {
                "topic": "Hot Key Handling",
                "why_important": "Even with perfect distribution, some keys are accessed far more than others (e.g., a viral tweet). The cache node responsible for a hot key becomes a bottleneck, and no amount of horizontal scaling of OTHER nodes helps.",
                "key_points": [
                    "Local cache (L1): each application instance caches hot keys in-process (Caffeine/Guava). Eliminates network hop for the hottest keys",
                    "Key replication: replicate hot keys across multiple cache nodes. Client reads from a random replica, spreading the load",
                    "Key splitting: split one logical key into N sub-keys (e.g., 'trending_post_v{0-9}'). Client reads from a random sub-key. All sub-keys have the same value",
                    "Detection: track per-key access frequency. When a key exceeds a threshold (e.g., 10K reads/second), automatically apply hot key treatment"
                ],
                "trade_offs": "Local cache is fastest but creates consistency issues (stale data across instances). Key replication uses more memory but gives consistent performance. Key splitting is a manual optimization that requires application-level awareness. The best approach is automatic hot key detection with local caching as the first line of defense."
            }
        ],
        "common_mistakes": [
            "Not addressing cache stampede — assuming expired items are simply re-fetched from DB without considering concurrent requests",
            "Using cache as the primary data store (write-back without durability) — cache crash causes permanent data loss",
            "Ignoring cache invalidation on writes — cache serves stale data indefinitely after a database update",
            "Not handling cache node failure — when a node dies, all its keys become misses, potentially overwhelming the database",
            "Treating all keys equally — not implementing special handling for hot keys that receive disproportionate traffic",
            "Setting identical TTL for all cached items — everything expires at the same time, causing a synchronized stampede",
            "Not monitoring cache hit rate — the most important metric for cache effectiveness, yet often overlooked"
        ],
        "solution_outline": {
            "entities": [
                "CacheEntry: {key, value (serialized bytes), ttl, created_at, access_count, version}",
                "CacheNode: {node_id, address, virtual_node_tokens: [int], status, memory_used, memory_limit}",
                "CacheCluster: {cluster_id, nodes: [CacheNode], hash_ring, replication_factor}",
                "EvictionPolicy: {type (LRU/LFU/TTL), max_memory, max_entries}"
            ],
            "api_sketch": [
                "GET /cache/{key} -> {value, ttl_remaining} or 404 (cache miss)",
                "PUT /cache/{key}  {value, ttl} -> 200",
                "DELETE /cache/{key} -> 200",
                "PUT /cache/{key}/cas  {value, expected_version} -> 200 or 409 (compare-and-swap for atomic updates)",
                "Internal: INVALIDATE_BROADCAST(key) -> notify all nodes/instances to invalidate local caches",
                "Admin: GET /cache/stats -> {hit_rate, miss_rate, eviction_rate, memory_used, hot_keys: [...]}"
            ],
            "components": [
                "Cache Client Library: consistent hashing for routing, connection pooling, local L1 cache for hot keys, serialization/deserialization",
                "Cache Server (per node): in-memory hash table with eviction policy, network interface (Redis protocol or custom), memory management",
                "Cluster Manager: monitors node health, manages hash ring, handles node addition/removal/rebalancing",
                "Replication Manager: synchronizes replicas for hot keys, handles failover when a node dies",
                "Stampede Prevention: mutex-based or probabilistic early expiry, stale-while-revalidate support",
                "Monitoring: per-node and per-key metrics (hit rate, latency p50/p99, memory utilization, eviction rate)",
                "Invalidation Bus: pub/sub channel for broadcasting cache invalidation events across nodes and application instances"
            ],
            "data_flow": "Read (cache-aside): Application -> Cache Client routes to correct node via consistent hashing -> Cache Server: lookup key in hash table -> if hit: return value, update LRU position -> if miss: return miss -> Application reads from DB -> Application writes to cache (PUT). Write (cache invalidation): Application writes to DB -> Application sends DELETE to cache -> if key is replicated: Invalidation Bus broadcasts to all replicas and local caches. Stampede prevention: on miss, Cache Client acquires distributed lock (SETNX) -> if acquired: read from DB, populate cache, release lock -> if not acquired: wait 50ms and retry (or serve stale if stale-while-revalidate is enabled)."
        },
        "teaching_notes": {
            "opening_question": "Your database is getting 10,000 reads/second and struggling. You add a cache and it drops to 500 reads/second. One day the cache goes down. What happens?",
            "key_insight": "A cache does not just improve performance — it becomes a critical dependency. The system must be designed assuming the cache WILL fail, popular items WILL expire simultaneously, and some keys WILL be disproportionately hot. Cache design is about the failure modes, not the happy path.",
            "scaffolding_hints": [
                "If they put data only in cache, ask: 'What happens when the cache server restarts and all data is lost?'",
                "If they ignore stampede, ask: 'A popular item expires. 1000 requests arrive in the next 100ms. How many hit the database?'",
                "If they use a single cache node, ask: 'How do you handle 1 million cached items that exceed one server's memory?'",
                "If they skip invalidation, ask: 'You update a user's profile in the database. The cache still has the old profile. When does the user see the new one?'"
            ],
            "when_to_push": "Push when the candidate designs only the happy path (cache hit) without addressing what happens on misses, stampedes, node failures, or stale data. These failure modes are the entire interview discussion.",
            "when_to_help": "Help if they are unfamiliar with consistent hashing — briefly explain the ring concept and why it minimizes key redistribution when nodes are added/removed."
        }
    }
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\nEnriching {len(ENRICHMENTS)} SD problems in '{db.name}.{col.name}'...\n")

    updated = 0
    not_found = 0

    for slug, fields in ENRICHMENTS.items():
        result = col.update_one({"slug": slug}, {"$set": fields})
        if result.modified_count:
            status = "UPDATED"
            updated += 1
        elif result.matched_count:
            status = "already up-to-date"
            updated += 1
        else:
            status = "NOT FOUND"
            not_found += 1
        print(f"  {slug}: {status}")

    print(f"\nDone. Updated: {updated}, Not found: {not_found}")

    # Verify enrichment
    print("\nVerification — checking fields on enriched documents:\n")
    expected_fields = [
        "level_expectations", "edge_cases", "follow_ups",
        "deep_dives", "common_mistakes", "solution_outline", "teaching_notes"
    ]
    for slug in ENRICHMENTS:
        doc = col.find_one({"slug": slug}, {f: 1 for f in expected_fields})
        if not doc:
            print(f"  {slug}: MISSING from DB")
            continue
        present = [f for f in expected_fields if f in doc]
        missing = [f for f in expected_fields if f not in doc]
        if missing:
            print(f"  {slug}: INCOMPLETE — missing {missing}")
        else:
            print(f"  {slug}: OK ({len(present)}/{len(expected_fields)} fields)")

    print()


if __name__ == "__main__":
    main()
