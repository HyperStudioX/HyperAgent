"use client";

import Image from "next/image";
import { useAuth } from "@/lib/hooks/use-auth";
import { LogOut, User } from "lucide-react";
import { cn } from "@/lib/utils";

export function UserMenu() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 px-1 py-1">
        <div className="w-8 h-8 rounded-full bg-secondary animate-pulse" />
        <div className="flex-1 h-4 w-24 bg-secondary animate-pulse rounded" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <button
        onClick={login}
        className={cn(
          "w-full flex items-center justify-center gap-2 h-9 px-4",
          "text-sm font-medium rounded-lg",
          "bg-foreground text-background",
          "hover:bg-foreground/90 transition-colors"
        )}
      >
        Sign In
      </button>
    );
  }

  return (
    <div className="group flex items-center gap-3 px-1 py-1 rounded-lg hover:bg-secondary/50 transition-colors">
      {/* Avatar */}
      {user?.image ? (
        <Image
          src={user.image}
          alt={user.name || "User"}
          width={32}
          height={32}
          unoptimized
          className="w-8 h-8 rounded-full"
        />
      ) : (
        <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
          <User className="w-4 h-4 text-muted-foreground" />
        </div>
      )}

      {/* Name */}
      <span className="flex-1 text-sm text-foreground truncate">
        {user?.name || user?.email}
      </span>

      {/* Logout */}
      <button
        onClick={logout}
        className={cn(
          "p-1.5 rounded-md opacity-0 group-hover:opacity-100",
          "text-muted-foreground hover:text-destructive",
          "hover:bg-destructive/10 transition-all"
        )}
        title="Sign out"
      >
        <LogOut className="w-4 h-4" />
      </button>
    </div>
  );
}
