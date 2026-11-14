## 10. Accounts and publishing

**Status.** Checklist. Head revision on main is `campaign_post_metrics`. Implement in the order below. Each box is one commit, and the console still works after that commit. Each box names the tests that land with it. Task 10.10 runs the full suites and `npm run build`.

**Goal.** Make one real live test possible. The operator creates a campaign, links Brendan's real social account, places a post, clicks Publish, and the assembled carousel goes out with its caption. Instagram and TikTok come first, through Ayrshare. OAuth happens in Ayrshare's dashboard, never in Twerva. The account row stores no token. The API key stays in the server environment. Mock stays the default adapter until that live test is proven.

**What the code does today.** Publish is selected by `get_publish_adapter` in `app/publish/factory.py`. `PUBLISH_ADAPTER` defaults to `mock` (`DEFAULT_PUBLISH_ADAPTER` in `app/settings.py`). `ayrshare` requires a non-blank `AYRSHARE_API_KEY` or the factory raises `PublishAdapterNotConfiguredError`. The key is unused by mock. `GET /health` does not load it.

`MockPublishAdapter.publish` and `publish_media` return `mock-{platform}-{id}` and `https://example.invalid/{platform}/p/{id}`. They log the media count and do not open the network. `AyrsharePublishAdapter` in `app/publish/ayrshare.py` stores the key on the instance and then raises `AyrshareLivePublishNotWiredError` from both methods. It does not call `AYRSHARE_POST_ENDPOINT` (`https://api.ayrshare.com/api/post`). `test_ayrshare_stub_publish_is_not_wired` in `apps/server/tests/test_publish_adapter.py` asserts that raise. The class comment says the later body is `post`, `platforms`, and `mediaUrls`, and that those URLs have to be publicly fetchable. Local `ARTIFACT_STORAGE_DIR` is not.

The campaign path is `publish_campaign_post` in `app/campaigns/posts.py`. `POST /api/v1/campaigns/{campaign_id}/posts/{post_id}/publish` calls it. `upcoming` and `failed` can publish. `posted` is 409, detail `This post is already up.` The route does not compare `scheduled_for` with the clock. The helper resolves each frame `asset_ref` with `resolve_asset_reference_path` under `ARTIFACT_STORAGE_DIR`. A missing file or a path that leaves the store sets `failed` and `last_error` and commits. Any other exception, including the Ayrshare refusal, does the same. Success sets `posted`, `published_at`, `platform_post_id`, and `platform_post_url`. The helper calls `publish_media(post_id, account, media_paths)`. It does not pass the caption. `CampaignPostRead.caption` is `assembled_carousels.caption`, which phase 7 set to the carousel name. `cta_url` is null. There is no hashtag column. The timeline does not append `campaigns.hashtag` or `DEFAULT_HASHTAGS`.

`CampaignTimelineRow` in `apps/ops/src/pages/CampaignTimeline.tsx` prints the status, the time, the handle, the caption, and the frames. `last_error` is already on `CampaignPostRead` and on the ops type. The row does not render it. `#publish-campaign-post` is the Publish button.

The old loop is still registered and off the rail. `publish_post_job` in `app/publish/service.py` calls `PublishAdapter.publish` with the artifact, whose caption is `build_carousel_caption` (interest title, `DEFAULT_HASHTAGS`, interest URL). Queue, Schedule, and Results are gone from `NAV_GROUPS`. This phase does not put them back.

Frames are PNGs at `assembled/{assembly_id}/{frame_id}.png`, 1080 by 1920 (`SKELETON_FRAME_WIDTH_PIXELS`, `SKELETON_FRAME_HEIGHT_PIXELS`). `GET /api/v1/carousels/{carousel_id}/assembly/frames/{frame_id}/file` serves one PNG to a signed-in reader. nginx does not serve `/opt/twerva/artifacts`. `docs/ops/deploy.md` says not to add a public artifacts location. The 1.6 spike's note that Twerva PNGs are 1080×1080 is stale. S3 is the housekeeping item in `docs/planning/phase_map.md` and is deferred. RDS, S3, and Secrets Manager stay deferred in the deploy runbook.

`accounts.external_account_id` is already a nullable text column. It is not part of the unique key (`platform`, `handle`). The model comment says not to add token columns. `AccountCreateRequest` already accepts `external_account_id`. `POST /api/v1/accounts` stores it. There is no PATCH. `AccountsPage` creates a row from cluster, platform, handle, and cadence cap, and does not send `external_account_id`. The accounts table does not show the column. Create and list sit on `accounts_router`, behind the session cookie. A reader may GET. Writes from a reader are 403 through `require_ops_operator_allowed_for_request`. The page does not call Ayrshare.

A campaign takes accounts only at create. `POST /api/v1/campaigns` writes `campaign_accounts`. `spotmu` requires at least one (`CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL`). `spotmu_test` may persist an empty list. `_raise_if_account_platforms_mismatch` rejects an account whose platform is not in the campaign's platform list (`Account platform is not in the campaign platform list.`). `place_campaign_post` rejects an account that is not in `campaign_accounts` (`That account is not on this campaign.`). `CampaignAccountList` on the campaign detail is read-only. `NewCampaignPage` is the only place that toggles accounts. Nothing attaches or detaches an account on a campaign that already exists.

The spike in `docs/reports/task_1_6_publish_spike.md` locks Ayrshare as the first live vendor: `POST https://api.ayrshare.com/api/post` with Bearer `AYRSHARE_API_KEY`, body `post`, `platforms`, and `mediaUrls`. It says an Instagram carousel takes up to 10 images, that the connected Instagram account is Business or Creator linked to a Facebook Page, and that a TikTok response may carry `id: "pending"` until an async webhook. It says to store the vendor profile id in `external_account_id` by hand. It does not name the profile-key header, the media-upload path, or the connection-check path. Those three are marked below as verify against Ayrshare's docs. Do not invent a field, a header, a limit, or an error code that the docs do not show. Where this sheet names one, it is the spelling to confirm first, and the docs win.

`docs/ops/deploy.md` still says optional `AYRSHARE_API_KEY` is unused and not to switch the box to `ayrshare`. systemd loads `/opt/twerva/database_url.env` and optionally `/opt/twerva/ops_auth.env` as `EnvironmentFile=` on `twerva-api`. The process does not open those files itself. `get_settings` caches the first successful load, so a new key is visible only after `sudo systemctl restart twerva-api`.

**Settled for this phase.** The tasks use these. The open decisions at the end are the choices Mu can still change.

- The live test posts one `campaign_posts` row through `publish_campaign_post` and `publish_media`. The operator presses Publish. Nothing reads the clock. `scheduled_for` is not sent to Ayrshare.
- `PUBLISH_ADAPTER` stays `mock` until the runbook step. CI and the default box do not call Ayrshare. Tests never open a real socket to `api.ayrshare.com`.
- OAuth stays in the Ayrshare dashboard. Twerva does not grow a redirect URL, a Meta app, or a TikTok app. No access token, refresh token, or expiry column is added to `accounts`. The API key stays in `AYRSHARE_API_KEY`. It is never written on a row, never returned by the API, and never logged.
- `external_account_id` is the Ayrshare profile key for the profile that owns that social account. It is not an OAuth token. The same key may sit on the Instagram row and the TikTok row when both accounts live on one Ayrshare profile. The ayrshare adapter refuses to publish when it is blank. Mock ignores it.
- One publish call targets the one account on the campaign post. `platforms` is that account's platform only. A second platform is a second post.
- The caption sent for a campaign post is `assembled_carousels.caption`. Today that is the carousel name. This phase does not append the campaign hashtag or `DEFAULT_HASHTAGS`, and it does not add a caption editor.
- Frames stay 1080×1920. This phase does not crop them. Media bytes reach Ayrshare through Ayrshare's media upload, not through a public Twerva URL and not through S3.
- Instagram over 10 images fails the post before any HTTP call. The frames are not truncated. A TikTok id of `pending` is stored as `platform_post_id`. There is no webhook and no poll.
- A failed publish still leaves the row `failed` with `last_error` set, which is what `publish_campaign_post` already does. The timeline shows that sentence. A retry uses the same Publish button.
- Paid ads stay out. Do not call an ads endpoint. Do not add Zernio or Postiz. Native Meta and TikTok stay deferred.

### Live HTTP

- [x] **10.1 Post through Ayrshare from both adapter methods**

  Replace the raise in `AyrsharePublishAdapter.publish` and `publish_media` with one HTTP call. Keep `AYRSHARE_POST_ENDPOINT`. The constructor still takes the API key and gains an optional `httpx.Client`. The factory passes no client, so production builds a normal client. Tests pass `httpx.Client(transport=httpx.MockTransport(...))`. Do not add `respx`. A test that forgets the transport must not be able to reach the network: the methods that talk HTTP take the client the constructor stored, and every test in this phase passes a mock transport. No test skips when offline.

  Add a pure builder, next to the adapter, that returns the JSON body and the headers. The body is `post` (the caption argument), `platforms` (a one-element list of `account.platform.value`, `instagram` or `tiktok`), and `mediaUrls` (the URL strings the caller supplies, in order). Do not send `scheduleDate`. The headers are `Authorization: Bearer` plus the API key, and the profile-key header when `external_account_id` strips to a non-empty string. The header name is not in the 1.6 spike. Confirm it against Ayrshare's docs before locking the spelling. The spelling to confirm first is `Profile-Key`. If the docs use another name, use that name. A blank `external_account_id` omits the header in this task. Task 10.4 turns that blank into a refusal before the request. The API key and the profile key are not logged. A log line may include the post id, the platform, the HTTP status, and the media count, the same facts `MockPublishAdapter` already logs.

  Send the body with `httpx`, the same library `OpenAITextGenerationProvider.draft_slide_text` uses. Timeout 30 seconds, the same number as that call. A transport error, a timeout, a status of 400 or above, a non-JSON body, or a JSON body that has no success entry for this platform raises `PublishError`. The message is the HTTP status plus a short vendor message when the body has one. Verify the success and error field names against Ayrshare's docs before locking the parse. The spike says the response includes a per-platform `id` and `postUrl`. Parse those names first. The message must not contain the API key or the profile key. `publish_campaign_post` and `publish_post_job` already catch that exception and store it on `last_error` with status `failed`. Do not add a second write path.

  `publish` passes `artifact.caption` (empty string when the caption is null) and, until task 10.2, does not invent URLs from local paths. `publish_media` takes the same caption argument, and this task's caller in `publish_campaign_post` passes `""`. Task 10.3 passes the assembled caption. Until task 10.2, both methods raise `PublishError` with a fixed detail before any HTTP call when they are handed filesystem paths and no URLs: `Publish media is not on a public URL yet.` That raise still becomes `failed` and `last_error`. It is the seam task 10.2 fills. `MockPublishAdapter.publish` and `publish_media` stay. Their signatures gain the caption argument only on the Ayrshare path if adding it to the abstract `publish_media` would force the mock to accept it. Prefer adding `caption: str` to `publish_media` on `PublishAdapter`, `MockPublishAdapter`, and `AyrsharePublishAdapter`. Mock ignores the string and still returns the fake id. Update the mock call sites.

  Delete `AyrshareLivePublishNotWiredError` once nothing raises it. Update `test_ayrshare_stub_publish_is_not_wired` and the factory test that still calls the class a stub. `get_publish_adapter` with `ayrshare` and a key still returns `AyrsharePublishAdapter`. With a blank key it still raises `PublishAdapterNotConfiguredError`. The default adapter is still `mock`. Update the module docstring in `app/settings.py` that says live HTTP is not wired. `docs/ops/deploy.md` stays on the old warning until task 10.8. Do not set `PUBLISH_ADAPTER=ayrshare` anywhere in the repo.

  On the campaign timeline, a failed row shows `last_error` under the status when it is non-null. A posted row does not show a stale error. `CampaignPostRead` already carries the field. This is the answer to the phase map question about what the operator sees when a post does not go out: status `failed` and that sentence. No new status.

  Acceptance, in `apps/server/tests/test_ayrshare_http.py` and an updated `test_publish_adapter.py`: a mock transport records one `POST` to `https://api.ayrshare.com/api/post`. The body `platforms` is `["instagram"]` for an Instagram account. The body `post` is the caption argument. The body `mediaUrls` is the URL list, in order. The `Authorization` header is `Bearer` plus the key. A non-blank `external_account_id` is sent on the profile-key header the docs confirmed. The handler's JSON `id` and `postUrl` come back as `PublishResult`. A status 400, a transport error, and a JSON body with no entry for the platform each raise `PublishError`, and the message does not contain the key. Calling `publish_media` with filesystem paths and no URLs raises the public-URL detail and the transport records no request. `MockPublishAdapter.publish_media` still returns `mock-{platform}-{post_id}` and does not open a client. `PUBLISH_ADAPTER` defaults to `mock`. In `apps/ops/campaignTimeline.test.ts`, a failed post renders its `last_error`, and a posted post does not.

### Media

- [x] **10.2 Upload frame files to Ayrshare before the post**

  Ayrshare has to fetch the images itself. The frame route requires a session cookie, and `/opt/twerva/artifacts` is not on nginx. Do not add an unauthenticated file route. Do not put a public alias in front of `ARTIFACT_STORAGE_DIR`. Do not take the S3 housekeeping item in this phase.

  The default is Ayrshare's media upload. Verify the path, the multipart field name, the response field that holds the URL, the size limit, and how long that URL stays fetchable against Ayrshare's docs. The spelling to confirm first is `POST https://api.ayrshare.com/api/media/upload` with the same Bearer key and the same profile-key header as the post, the file bytes in the multipart body, and a URL string in the JSON response. Use the documented path and field names when they differ. Upload each frame in position order. Collect the returned URLs. Pass that list as `mediaUrls` into the post from task 10.1. One upload failure raises `PublishError` and does not call the post endpoint. The bytes come from the paths `publish_campaign_post` already resolved. The adapter reads the files. It does not take a public Twerva URL.

  If the verified docs have no upload, or the upload is missing on the plan Mu holds, stop and use the fallback in open decision 1. Do not invent a third host. The fallback is a short-lived signed URL served by Twerva, still not a standing public directory. S3 stays the later move for more than one machine.

  `publish` for a post job uses the same upload on `resolve_artifact_slide_media_paths`. The campaign path is the one the live test uses. Drop the public-URL raise from task 10.1 on these two methods once the URLs come from the upload. Timeout for the upload starts at 60 seconds, because a set of 1080×1920 PNGs is larger than the chat completion that uses 30. If the docs name a limit, use that limit.

  Acceptance, in `test_ayrshare_http.py`: two PNG paths produce two upload requests and then one post. The post's `mediaUrls` are the two URL strings the upload handler returned, in frame order. A failed upload records no post request and raises `PublishError`. The frame file route still requires a session. No test calls the network.

### Caption

- [x] **10.3 Send the assembled caption**

  `publish_campaign_post` passes `stored_post.assembled_carousel.caption` into `publish_media`. Null becomes `""`. The string is whatever assemble stored. This task does not read `campaigns.hashtag`, does not call `build_carousel_caption`, and does not append `DEFAULT_HASHTAGS`. It does not add a column and does not add an editor on the timeline. The caption line already on the row is the string that is sent.

  `publish` keeps passing `artifact.caption` for the old post-job path. That path is not the live test.

  Acceptance, in `test_ayrshare_http.py` or `test_campaign_posts.py`: a campaign post whose assembled caption is the carousel name sends that name as `post`. A guidance-style hashtag string is not added. An empty caption is sent as `""` and still attempts the post. Mock publish still ignores the caption and still returns the fake id.

### Profile binding

- [x] **10.4 Set the Ayrshare profile key on the account, and refuse a live publish without it**

  No migration. `external_account_id` is already on `accounts` and on `AccountReadResponse`. Do not add a token column.

  `PATCH /api/v1/accounts/{account_id}` with `{external_account_id}`. Admin writes follow the existing cookie rule: a reader is 403. Unknown id is 404. The response is `AccountReadResponse`. Null, or a string that strips to empty, stores null. Any other string stores the stripped value. The route does not call Ayrshare. The route does not accept `platform`, `handle`, `cluster_id`, or `cadence_cap_per_day` in this task. Register the path on `accounts_router` and add it to `EXPECTED_API_V1_PATHS` in `apps/server/tests/test_api_routes.py`.

  On the ayrshare adapter, a blank `external_account_id` raises `PublishError` before upload and before the post. The detail is `This account has no Ayrshare profile key. Set external_account_id before publishing.` `publish_campaign_post` stores that on `last_error` and sets `failed`. Mock publish does not read the column. A campaign post on the mock adapter still posts when the column is null.

  `AccountsPage` shows the column on the accounts table. An admin can set it on create and edit it on an existing row. Create already has a client field for it in `AccountCreateRequest`; the form in `handleCreateAccount` does not send it today, so the create form gains an optional input and passes it through `createAccount`. Edit calls `patchAccount` in `apps/ops/src/api/client.ts`. A reader sees the value and cannot save. The input's label says it is the Ayrshare profile key, and that the API key stays on the server. The page does not collect a password, an OAuth code, or `AYRSHARE_API_KEY`.

  Acceptance, in `apps/server/tests/test_accounts.py`: an admin PATCH stores the key, a blank string stores null, a reader is rejected, and an unknown id is 404. Create with the field set still returns it. In `test_ayrshare_http.py`, a blank `external_account_id` raises the detail above and the mock transport records no request. A mock-adapter campaign publish with a null column still becomes `posted`. The accounts table renders the key, and the create body includes it when the field is filled. Cover that helper in `apps/ops` next to the page, in a small test module. There is no accounts page test today.

### Campaign accounts

- [x] **10.5 Attach and detach an account on an existing campaign**

  No migration. `campaign_accounts` is already the join, unique on `(campaign_id, account_id)`, cascade on both deletes.

  `POST /api/v1/campaigns/{campaign_id}/accounts` with `{account_id}`. Admin only, same as `create_campaign`. Unknown campaign or unknown account is 404. The account's platform has to be in the campaign's platform list, using `_raise_if_account_platforms_mismatch` and the same detail. A second link for the same pair is 409, detail `That account is already on this campaign.` The response is the campaign detail from `serialize_campaign`, so `accounts` includes the new row. The helper does not create a post and does not publish.

  `DELETE /api/v1/campaigns/{campaign_id}/accounts/{account_id}`. Admin only. A missing link is 404. When any `campaign_posts` row on this campaign uses that account, including `upcoming`, `posted`, and `failed`, the link stays and the route returns 409, detail `This account stays on the campaign because a post uses it.` Otherwise the join row is deleted and the account row stays. The response is the campaign detail. Add both paths to `EXPECTED_API_V1_PATHS`.

  On the campaign detail, `CampaignAccountList` gains attach and detach for an admin. Attach lists accounts whose platform is already on the campaign and which are not linked yet. Detach calls the delete route. A 409 shows the API detail in `ErrorBanner`. A reader sees the list and both controls disabled. Create on `NewCampaignPage` stays as it is. `spotmu` still requires an account at create. After this task a `spotmu_test` campaign can gain an account without being recreated, and the timeline's account choices update from `selectedCampaign.accounts`.

  Acceptance, in `apps/server/tests/test_campaigns.py`: an admin attaches an Instagram account to a campaign whose platforms include Instagram, and the detail lists it. A TikTok account on an Instagram-only campaign is 400 and the link count stays. A duplicate attach is 409. Detach removes the link and leaves the account. Detach is 409 while an upcoming post uses that account, and the link remains. A reader is rejected. In an ops test, an admin with one unlinked matching account can attach, and a reader cannot.

### Platform limits

- [x] **10.6 Enforce the Instagram image cap, and store a TikTok pending id**

  Before upload, when the account platform is `instagram` and the media list has more than 10 files, raise `PublishError` with a detail that states the cap and the actual count. Do not upload, do not POST, and do not drop frames to make ten. The constant lives next to the adapter. The spike says 10. Verify the current cap against Ayrshare's docs and change the constant if the docs disagree. Do not invent a TikTok cap. If the docs name one, apply it the same way, as a refuse, not a truncate. Otherwise TikTok has no local count check in this task.

  On the response parse from task 10.1, an id whose value is the documented pending token is still a success. The spike says TikTok may return `id: "pending"`. Verify that token and which field holds it. Store it as `platform_post_id`. Store `postUrl` when the entry has one, and leave `platform_post_url` null when it does not. The row becomes `posted`. Do not sleep, poll, or register a webhook. A later phase can replace a pending id. A response the docs call an error is still `PublishError`, even if an id is present.

  One retry of a `failed` row sends the upload and the post again. This phase does not add an idempotency key. Verify whether Ayrshare documents one, and add it only when the docs name the header or field. Until then, a timeout after Ayrshare has accepted the post can double-post on retry. The live checklist tells Mu to look at the social account before pressing Publish again on a timeout.

  Acceptance, in `test_ayrshare_http.py`: eleven Instagram paths raise before the transport records a request, and the detail names 10 and 11. Ten paths reach upload. A TikTok body whose id is `pending` and whose URL is absent returns `platform_post_id` `pending` and a null URL, and `publish_campaign_post` stores `posted`. A vendor error body leaves the row `failed` and does not store `pending` as a success.

### Connection check

- [x] **10.7 Check the key and the profile without posting**

  Add a read on the ayrshare adapter, separate from `publish` and `publish_media`. It sends one GET with the Bearer key and, when the account's `external_account_id` is set, the same profile-key header. It does not send `post` or `mediaUrls`. Verify the path against Ayrshare's docs. The spelling to confirm first is `GET https://api.ayrshare.com/api/user`. If the docs say a profile is read from a different path, use that path. Parse the connected platforms or handles the docs return. A transport error or a non-success status raises `PublishError` with the same rule as task 10.1: status plus a short vendor message, and neither secret in the message.

  `GET /api/v1/accounts/{account_id}/connection`. Admin only. Unknown account is 404. The response is `{adapter, ok, detail}`. `ok` true means the call returned the documented success shape. `detail` is a short sentence naming the connected platforms the body listed, or the error sentence. The response does not include the API key or the profile key. On the mock adapter the method does not open a client and returns `adapter` `mock`, `ok` true, and a detail that says the mock adapter does not call Ayrshare. Selecting ayrshare with a blank `AYRSHARE_API_KEY` still fails at `get_publish_adapter` with `PublishAdapterNotConfiguredError`, which this route returns as a 409 and `ok` false rather than posting. The route does not change the account row and does not create a post.

  `AccountsPage` shows `#check-account-connection` on each account row, labeled `Check connection`. An admin click calls the route and shows `detail` in the status line, or in `ErrorBanner` when the request fails. A reader sees the button disabled. The button does not call `publishCampaignPost`.

  Acceptance, in `test_ayrshare_http.py` and `test_accounts.py`: the mock transport records one GET and no POST. The bearer header is set. A profile key is sent on the profile header. The response `detail` does not contain the key. A status 401 returns `ok` false and does not write `external_account_id`. The mock adapter returns `ok` true without a request. A reader is rejected. An ops helper test covers the disabled reader and the detail string.

### Runbook

- [x] **10.8 Document the production switch, with mock as the rollback**

  Update the Phase 1.6 section of `docs/ops/deploy.md`. That section currently says not to switch the box to `ayrshare`. Replace that warning with the phase 10 order. Do not invent AWS console steps. Do not paste a real key.

  The order on `twerva-server` is: put `AYRSHARE_API_KEY` in an `EnvironmentFile` `twerva-api` already loads (`/opt/twerva/database_url.env` or `/opt/twerva/ops_auth.env`), mode 600, then `sudo systemctl restart twerva-api`, and leave `PUBLISH_ADAPTER=mock`. The operator runs Check connection from Accounts. Only after that check names the expected profile, set `PUBLISH_ADAPTER=ayrshare` in the same file and restart again. Rollback is setting `PUBLISH_ADAPTER=mock` and restarting. The key may stay in the file. Rollback does not delete posts and does not need a downgrade. There is no Alembic revision in this phase. `get_settings` caches the first load, so the restart is what picks up the new values. Keep the existing sentence that the process does not open the env file itself.

  The secrets table in that doc gains `AYRSHARE_API_KEY` as a line in one of those two files, not a new file and not a git secret. `OPENAI_API_KEY` stays the text-generation key. The two keys are not interchangeable. The section still says not to print the file.

  Acceptance: the Phase 1.6 section states the two-step switch and the mock rollback. It does not tell the operator to set `ayrshare` before the connection check. No application default changes. `DEFAULT_PUBLISH_ADAPTER` stays `mock`.

### Dry run

- [x] **10.9 Dry-run the live path against a mocked Ayrshare, and leave Mu a checklist**

  One server test walks the campaign path with `PUBLISH_ADAPTER=ayrshare`, a fake key, and an `httpx.MockTransport` installed on the adapter the route uses. The test creates no real socket. The fixture is a campaign, one linked account with `external_account_id` set, and one upcoming post whose assembled carousel has two frames on disk and a caption. `POST .../publish` returns `posted`. The transport saw one upload per frame and one post. The post body carried the caption, `platforms` of that one account, and the upload URLs. The stored `platform_post_id` and `platform_post_url` are the handler's values. A second case with a blank `external_account_id` returns `failed`, `last_error` set, and no post request. `POST /api/v1/generate/carousel` and `publish_post_job` are not required for this test.

  Add the manual live-test checklist to the phase 10 section of `docs/ops/deploy.md`, under the switch from task 10.8. It is for Mu, on the real box, after he has done the items in "What Mu must do himself." The checklist is:

  1. `PUBLISH_ADAPTER` is still `mock`. Check connection on Brendan's account row and read a failure or a mock detail, not a live post.
  2. Set the API key, restart, leave the adapter on `mock`, and run Check connection again only after task 10.8's switch to `ayrshare`. The detail names the platform he connected. It does not print the key.
  3. Create a Spotmu campaign, attach Brendan's account if it was not linked at create, assemble a carousel of at most 10 frames, add it to the timeline, and press Publish once.
  4. The row reads `posted`, the platform URL opens the carousel, and the caption is the carousel name. A `failed` row shows `last_error`.
  5. Before pressing Publish again on a timeout, look at the Instagram or TikTok account so a second press does not double-post.
  6. Rollback is `PUBLISH_ADAPTER=mock` and a restart. The next Publish on a new post stays on `example.invalid`.

  This commit does not post to the real API and does not change the default adapter.

  Acceptance: the dry-run test passes with the mock transport and fails closed on a blank profile key. The checklist is in `docs/ops/deploy.md`. No test contacts `api.ayrshare.com`.

### Tests

- [x] **10.10 Run the full server suite, the full ops suite, and the ops build**

  From `apps/server`, `python -m unittest discover -s tests`. From `apps/ops`, `node --test *.test.ts`, then `npm run build`. This commit adds no product behavior. It fixes failures that this phase's tasks left, and it does not start a new feature. Migration tests that skip because Postgres is down stay skipped, the same way `test_carousel_steps_migration.py` skips. A skip is not a failure. The phase is done when both suites pass aside from those skips, and `npm run build` succeeds.

### What Mu must do himself

Twerva cannot do these. They happen outside the repo.

- Create an Ayrshare account and a plan that allows the API used above. Verify which plan includes the post call, the media upload, and profile keys. This sheet does not name a price or a plan tier.
- In the Ayrshare dashboard, connect Brendan's Instagram as a Business or Creator account linked to a Facebook Page, and/or connect Brendan's TikTok. The OAuth consent stays on Ayrshare's site. Twerva never sees the Instagram or TikTok password.
- Put the Ayrshare API key in the server environment as `AYRSHARE_API_KEY`. Put the profile key on the Twerva account row through Accounts, in `external_account_id`. Do not commit either value and do not paste them into chat.
- Confirm `OPENAI_API_KEY` is set if the slides should be generated. A carousel someone typed still assembles and still publishes with no OpenAI key. `TEXT_GENERATION_PROVIDER=fake` is the local draft path and is not the live post.

The first connection is Brendan's account. Mu owns that login.

### Open decisions

These are the questions section 10 leaves open. The tasks above use the recommended default so a commit can name a file. Anything about Ayrshare's API that this sheet is not sure of says verify against Ayrshare's docs.

1. **How Ayrshare fetches the frames.** The choices are Ayrshare's media upload, a short-lived signed URL served by Twerva, or S3. Recommended default: Ayrshare's media upload. The frame route is behind the session cookie, `ARTIFACT_STORAGE_DIR` is not public, and the deploy runbook says not to add a public artifacts location. A signed URL would open a new unauthenticated path on `twerva.com` for the time it is valid. S3 is the deferred housekeeping move for when more than one machine needs the bytes, and this phase does not need that. Upload keeps the API key on the server and keeps the disk private. Verify the upload path, the multipart field, the URL field in the response, the size limit, and how long the URL lives. The spelling to confirm first is `POST https://api.ayrshare.com/api/media/upload`. If that call is absent from the docs or missing on Mu's plan, the fallback is a short-lived signed URL on Twerva, still not a standing public directory. S3 stays out either way.
2. **Where the caption comes from.** Recommended default: `assembled_carousels.caption`, which assemble sets to the carousel name. `publish_media` sends that string as Ayrshare's `post` field. The timeline already shows it. This phase does not append `campaigns.hashtag` or `DEFAULT_HASHTAGS`, and it does not add an editor. A rename of the carousel after assemble does not change the stored caption. Say if the operator should type a caption on the post, or if the campaign hashtag should be appended.
3. **Whether a post goes out at `scheduled_for`.** Recommended default: deferred. The operator clicks Publish. The time may be in the past. No worker reads the clock, and the Ayrshare body does not include `scheduleDate`. A scheduler, in Twerva or at Ayrshare, is a later phase. Say if Publish should hand the time to Ayrshare and let them wait.
4. **Instagram's 10-image cap and TikTok's pending id.** Recommended default: both are in scope, and both stay small. More than 10 Instagram frames fails the post before HTTP, with `last_error` set, and does not drop frames. Verify the cap. The spike says 10. A TikTok id of `pending` is stored as `platform_post_id`, the URL is stored when the response has one, and the row is `posted`. Verify the token and the field. There is no webhook and no poll. A webhook receiver is deferred with phase 11. Say if TikTok should be left off the live test until the id is final, or if a count over 10 should publish the first 10.
5. **One Ayrshare profile or many.** Recommended default: one profile for the first test. The API key is the business key in the environment. `external_account_id` stores that profile's key, and the Instagram row and the TikTok row may store the same key. The adapter sends it on the profile-key header. Verify the header name. The spelling to confirm first is `Profile-Key`. A blank value refuses the ayrshare publish and does not fall through to the primary profile. Verify whether a primary profile can post with no profile header. This phase still requires the key, so a missing link fails closed. A later second profile is another key on another row. There is no profiles table. Say if the primary profile should be allowed to publish with the column null.
6. **Frame shape.** Assembled frames are 1080×1920. The 1.6 spike's 1080×1080 note is stale. Recommended default: upload the PNG as assembled. Do not crop or resize in this phase. Verify whether Instagram, through Ayrshare, accepts a 9:16 image in a carousel. A rejection comes back as `failed` and `last_error`. Say if the live test should letterbox to a square or to 4:5 first.
7. **One call, one platform.** Recommended default: `platforms` is the single account on the campaign post. Instagram and TikTok are two posts on two rows. Do not ask Ayrshare to fan out one carousel to every connected profile. Say if one press should post to every account linked on the campaign.
8. **Which read proves the connection.** Recommended default: one GET, no post, shown on Accounts as Check connection. Verify the path. The spelling to confirm first is `GET https://api.ayrshare.com/api/user`, with the profile-key header when the row has one. The screen shows the connected platforms or the error sentence, and neither secret. Say if the check should hit a profiles list instead, or if it should run without a profile key and only prove the API key.

### Out of scope

- A worker that publishes when `scheduled_for` arrives. Celery and Redis stay out. Ayrshare `scheduleDate` stays out.
- Phase 11. No pull of views, likes, comments, shares, or saves from Ayrshare. The manual result route and the mock stub stay as phase 9 left them.
- Native Meta and TikTok app review, Instagram content-publish containers, and TikTok's audit. OAuth redirect URLs on Twerva. Token columns on `accounts`.
- A public artifacts location, a standing signed-URL directory, and the S3 move.
- Paid ads, and any ads endpoint on Ayrshare, Zernio, or elsewhere.
- Postiz, a self-hosted scheduler, and a second vendor adapter. Zernio stays the swap noted in the 1.6 spike if Ayrshare's pricing or the pending id becomes painful. This phase does not build that swap.
- Cropping the 1080×1920 frame, a caption editor, campaign rules, and a webhook for the TikTok pending id.
