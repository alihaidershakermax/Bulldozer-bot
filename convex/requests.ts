import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    userId: v.string(),
    username: v.string(),
    fileType: v.string(),
    pages: v.number(),
    lines: v.number(),
    status: v.string(),
    error: v.optional(v.string()),
    createdAt: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("requests", args);
  },
});

export const list = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 50;
    return await ctx.db.query("requests").order("desc").take(limit);
  },
});

export const stats = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("requests").collect();
    const uniqueUsers = new Set(all.map((r) => r.userId)).size;
    return {
      total: all.length,
      success: all.filter((r) => r.status === "success").length,
      error: all.filter((r) => r.status === "error").length,
      uniqueUsers,
      totalPages: all.reduce((s, r) => s + (r.pages || 0), 0),
      totalLines: all.reduce((s, r) => s + (r.lines || 0), 0),
    };
  },
});

export const userStats = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const all = await ctx.db
      .query("requests")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .collect();
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    const month = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    const year  = new Date(now.getFullYear(), 0, 1).toISOString();
    return {
      total: all.length,
      today: all.filter((r) => r.createdAt >= today).length,
      month: all.filter((r) => r.createdAt >= month).length,
      year:  all.filter((r) => r.createdAt >= year).length,
    };
  },
});

export const dailyCount = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    const all = await ctx.db
      .query("requests")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .collect();
    return all.filter((r) => r.createdAt >= today && r.status === "success").length;
  },
});

export const remove = mutation({
  args: { id: v.id("requests") },
  handler: async (ctx, { id }) => {
    await ctx.db.delete(id);
    return { success: true };
  },
});
