import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  requests: defineTable({
    userId: v.string(),
    username: v.string(),
    fileType: v.string(),
    pages: v.number(),
    lines: v.number(),
    status: v.string(),
    error: v.optional(v.string()),
    createdAt: v.string(),
  })
    .index("by_userId", ["userId"])
    .index("by_status", ["status"])
    .index("by_createdAt", ["createdAt"]),

  users: defineTable({
    userId: v.string(),
    username: v.string(),
    fullName: v.string(),
    firstSeen: v.string(),
    lastActive: v.string(),
    isBanned: v.optional(v.boolean()),
    banReason: v.optional(v.string()),
  })
    .index("by_userId", ["userId"])
    .index("by_isBanned", ["isBanned"]),

  settings: defineTable({
    key: v.string(),
    value: v.string(),
  }).index("by_key", ["key"]),

  admins: defineTable({
    userId: v.string(),
    addedAt: v.string(),
  }).index("by_userId", ["userId"]),
});
