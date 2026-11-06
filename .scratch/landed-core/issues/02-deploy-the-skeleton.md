# 02: Deploy the skeleton

**What to build:** The skeleton from ticket 01 runs at public URLs: the API on Render's free tier in Singapore, next to Neon, and the web app on Vercel. The browser reaches the API through a Vercel rewrite, so the sign-in cookie stays first-party and CORS isn't needed.

**Blocked by:** 01

**Status:** ready-for-agent, except the part marked ready-for-human below

**Scheduled:** Friday night, after 01, 04 and 03

## ready-for-agent

- [ ] The repo holds the Render and Vercel config, including the rewrite from `/api/*` to Render
- [ ] Migrations and the seed have a documented command to run against Neon
- [ ] Once the human part below is done, the live web app shows the API as reachable through the rewrite

## ready-for-human

These are Aamir's steps.

- [ ] Create the Render and Vercel accounts and connect them to the repo
- [ ] Set the environment variables on Render and Vercel, using the names in `.env.example`. `DATABASE_URL_TEST` stays local
- [ ] Set up the uptime ping every 10 minutes
