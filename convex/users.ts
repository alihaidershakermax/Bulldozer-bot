import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const upsert = mutation({
  args: {
    userId: v.string(),
    username: v.string(),
    fullName: v.string(),
    now: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        username: args.username,
        fullName: args.fullName,
        lastActive: args.now,
      });
      return { isNew: false };
    }

    await ctx.db.insert("users", {
      userId: args.userId,
      username: args.username,
      fullName: args.fullName,
      firstSeen: args.now,
      lastActive: args.now,
      isBanned: false,
    });
    return { isNew: true };
  },
});

export const updateActivity = mutation({
  args: { userId: v.string(), now: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { lastActive: args.now });
    }
  },
});

export const ban = mutation({
  args: { userId: v.string(), reason: v.optional(v.string()) },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, {
        isBanned: true,
        banReason: args.reason ?? "",
      });
      return { success: true };
    }
    await ctx.db.insert("users", {
      userId: args.userId,
      username: "",
      fullName: "",
      firstSeen: new Date().toISOString(),
      lastActive: new Date().toISOString(),
      isBanned: true,
      banReason: args.reason ?? "",
    });
    return { success: true };
  },
});

export const unban = mutation({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { isBanned: false, banReason: "" });
      return { success: true };
    }
    return { success: false };
  },
});

export const isBanned = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const u = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    return {
      banned: u?.isBanned ?? false,
      reason: u?.banReason ?? "",
    };
  },
});

export const listBanned = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("users")
      .withIndex("by_isBanned", (q) => q.eq("isBanned", true))
      .collect();
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("users").order("desc").collect();
  },
});

export const listActive = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 20;
    const all = await ctx.db.query("users").order("desc").take(limit);
    return all.sort((a, b) => b.lastActive.localeCompare(a.lastActive));
  },
});

export const count = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("users").collect();
    return all.length;
  },
});
