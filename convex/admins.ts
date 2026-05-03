import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const add = mutation({
  args: { userId: v.string(), addedAt: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("admins")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    if (existing) return { success: true, alreadyExists: true };
    await ctx.db.insert("admins", {
      userId: args.userId,
      addedAt: args.addedAt,
    });
    return { success: true, alreadyExists: false };
  },
});

export const remove = mutation({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("admins")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    if (existing) {
      await ctx.db.delete(existing._id);
      return { success: true };
    }
    return { success: false };
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("admins").order("desc").collect();
  },
});

export const isAdmin = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const row = await ctx.db
      .query("admins")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    return { isAdmin: row !== null };
  },
});
