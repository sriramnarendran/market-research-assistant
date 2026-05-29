import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Globe, Link2, Lightbulb, Loader2, Plus, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { api, ApiError } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  MAX_TOPIC_LEN,
  MAX_TOPICS,
  validateTopicDraft,
  validateTopicList,
} from "@/lib/topicValidation";
import { validateUrlList } from "@/lib/urlValidation";
import { cn } from "@/lib/utils";

const MAX_URLS = 5;

const EXAMPLE_TOPICS = ["Notion AI", "Microsoft Copilot"];
const EXAMPLE_URLS =
  "https://www.notion.com/blog/notion-ai-connectors\nhttps://blogs.microsoft.com/blog/2024/03/13/";

export function CreateRunPage() {
  const navigate = useNavigate();
  const [topics, setTopics] = useState<string[]>([]);
  const [topicDraft, setTopicDraft] = useState("");
  const [topicError, setTopicError] = useState<string | null>(null);
  const [urlsText, setUrlsText] = useState("");
  const [urlErrors, setUrlErrors] = useState<{ url: string; message: string }[]>([]);

  const { data: runs } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
  });
  const showOnboarding = runs !== undefined && runs.length === 0;
  const hasHistory = (runs?.length ?? 0) > 0;

  const mutation = useMutation({
    mutationFn: api.createRun,
    onSuccess: (resp) => {
      toast.success("Research started — opening progress…");
      navigate(`/runs/${resp.id}`);
    },
    onError: (e) => {
      toast.error("Could not start research", {
        description: e instanceof ApiError ? e.message : "Something went wrong",
      });
    },
  });

  function addTopic(raw: string) {
    const err = validateTopicDraft(raw);
    if (err) {
      setTopicError(err);
      return;
    }
    const t = raw.trim();
    if (!t) return;
    if (topics.length >= MAX_TOPICS) {
      toast.error(`Maximum ${MAX_TOPICS} topics`);
      return;
    }
    if (topics.includes(t)) return;
    setTopics([...topics, t]);
    setTopicDraft("");
    setTopicError(null);
  }

  function removeTopic(t: string) {
    setTopics(topics.filter((x) => x !== t));
  }

  function parsedUrls(): string[] {
    return urlsText
      .split(/\r?\n/)
      .map((u) => u.trim())
      .filter((u) => u.length > 0);
  }

  function fillExample() {
    setTopics(EXAMPLE_TOPICS);
    setUrlsText(EXAMPLE_URLS);
    toast.message("Example loaded — edit or replace before starting");
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const us = parsedUrls();
    if (topics.length === 0 && us.length === 0) {
      toast.error("Add at least one topic or URL to research");
      return;
    }
    if (us.length > MAX_URLS) {
      toast.error(`Maximum ${MAX_URLS} URLs`);
      return;
    }
    const invalidTopics = validateTopicList(topics);
    if (invalidTopics.length > 0) {
      toast.error("Fix invalid topics before starting", {
        description: invalidTopics.map((e) => `${e.topic}: ${e.message}`).join("; "),
      });
      return;
    }
    const invalid = validateUrlList(us);
    if (invalid.length > 0) {
      setUrlErrors(invalid);
      toast.error("Fix invalid URLs before starting", {
        description: invalid.map((e) => `${e.url}: ${e.message}`).join("; "),
      });
      return;
    }
    setUrlErrors([]);
    mutation.mutate({ topics, urls: us });
  }

  const urlCount = parsedUrls().length;
  const canSubmit = topics.length > 0 || urlCount > 0;
  const topicDraftTrimmed = topicDraft.trim();
  const topicDraftLen = topicDraftTrimmed.length;
  const topicAtMax = topics.length >= MAX_TOPICS;
  const topicDraftInvalid = topicDraftLen > 0 ? validateTopicDraft(topicDraft) : null;
  const showTopicError = topicError ?? topicDraftInvalid;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        title="Start research"
        description="Add competitors or topics for web search, paste URLs to analyze directly, or both. You'll get a cited report in a few minutes."
        actions={
          hasHistory ? (
            <Button variant="outline" size="sm" asChild>
              <Link to="/runs">View history</Link>
            </Button>
          ) : undefined
        }
      />

      {showOnboarding && (
        <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Lightbulb className="h-4 w-4" />
              </span>
              First time here?
            </CardTitle>
            <CardDescription className="space-y-3 pt-1">
              <p>
                We search the web for your topics, read any URLs you provide, then write a
                structured report. Each claim is verified against its sources automatically.
              </p>
              <Button type="button" variant="secondary" size="sm" onClick={fillExample}>
                Load an example
              </Button>
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      <form onSubmit={onSubmit} className="space-y-5">
        <FormStep
          step={1}
          title="Topics to research"
          description={`Competitors, products, or themes — we'll search the web (${topics.length}/${MAX_TOPICS})`}
          icon={Globe}
          accent="sky"
        >
          <div className="space-y-2">
            <div className="flex gap-2">
              <div className="min-w-0 flex-1 space-y-1">
                <Label htmlFor="topic-draft" className="sr-only">
                  Topic
                </Label>
                <Input
                  id="topic-draft"
                  value={topicDraft}
                  onChange={(e) => {
                    setTopicDraft(e.target.value);
                    if (topicError) setTopicError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTopic(topicDraft);
                    }
                  }}
                  placeholder="e.g. Salesforce Agentforce"
                  maxLength={MAX_TOPIC_LEN}
                  aria-invalid={showTopicError != null}
                  aria-describedby="topic-draft-hint"
                  disabled={topicAtMax}
                  className={cn(showTopicError && "border-destructive focus-visible:ring-destructive/30")}
                />
                <div id="topic-draft-hint" className="flex items-center justify-between gap-2 px-0.5">
                  <p className="text-xs text-muted-foreground">
                    {topicAtMax
                      ? `Maximum ${MAX_TOPICS} topics reached — remove one to add another.`
                      : `Up to ${MAX_TOPIC_LEN} characters per topic.`}
                  </p>
                  <p
                    className={cn(
                      "shrink-0 text-xs tabular-nums",
                      topicDraftLen > MAX_TOPIC_LEN
                        ? "font-medium text-destructive"
                        : topicDraftLen >= MAX_TOPIC_LEN - 10
                          ? "text-amber-700"
                          : "text-muted-foreground",
                    )}
                  >
                    {topicDraftLen}/{MAX_TOPIC_LEN}
                  </p>
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                className="self-start"
                disabled={!topicDraftTrimmed || topicDraftInvalid != null || topicAtMax}
                onClick={() => addTopic(topicDraft)}
              >
                <Plus className="h-4 w-4" />
                <span className="sr-only sm:not-sr-only sm:ml-0">Add</span>
              </Button>
            </div>
            {showTopicError && (
              <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                {showTopicError}
              </p>
            )}
          </div>
          {topics.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {topics.map((t) => (
                <button
                  type="button"
                  key={t}
                  onClick={() => removeTopic(t)}
                  className="group inline-flex items-center gap-1.5 rounded-full border bg-secondary/80 px-3 py-1.5 text-sm transition-colors hover:border-destructive/30 hover:bg-destructive/5"
                  title="Click to remove"
                >
                  {t}
                  <X className="h-3.5 w-3.5 text-muted-foreground group-hover:text-destructive" />
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Optional if you only have specific URLs — skip to step 2.
            </p>
          )}
        </FormStep>

        <FormStep
          step={2}
          title="Source URLs"
          description={`Articles, press releases, or docs — one URL per line (${urlCount}/${MAX_URLS})`}
          icon={Link2}
          accent="violet"
        >
          <Label htmlFor="urls" className="sr-only">
            URLs
          </Label>
          <Textarea
            id="urls"
            value={urlsText}
            onChange={(e) => {
              setUrlsText(e.target.value);
              if (urlErrors.length > 0) setUrlErrors([]);
            }}
            rows={5}
            placeholder={"https://company.com/blog/product-launch\nhttps://news.example.com/article"}
            className="rounded-lg font-mono text-xs shadow-sm"
            aria-invalid={urlErrors.length > 0}
          />
          {urlErrors.length > 0 && (
            <ul className="space-y-1 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {urlErrors.map((err) => (
                <li key={err.url}>
                  <span className="font-mono">{err.url}</span> — {err.message}
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted-foreground">
            Each line must be a full http or https link. Unreachable links are skipped when topics
            are also provided.
          </p>
        </FormStep>

        <Card
          className={cn(
            "overflow-hidden transition-colors",
            canSubmit ? "border-primary/25 bg-primary/[0.03]" : "border-dashed",
          )}
        >
          <CardContent className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3 text-sm text-muted-foreground">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Sparkles className="h-4 w-4" />
              </span>
              <p className="leading-relaxed">
                {canSubmit ? (
                  <>
                    Ready to research{" "}
                    {topics.length > 0 && (
                      <strong className="text-foreground">
                        {topics.length} topic{topics.length === 1 ? "" : "s"}
                      </strong>
                    )}
                    {topics.length > 0 && urlCount > 0 && " and "}
                    {urlCount > 0 && (
                      <strong className="text-foreground">
                        {urlCount} URL{urlCount === 1 ? "" : "s"}
                      </strong>
                    )}
                    . Progress updates live on the next screen.
                  </>
                ) : (
                  "Add at least one topic or URL above to continue."
                )}
              </p>
            </div>
            <Button
              type="submit"
              disabled={mutation.isPending || !canSubmit}
              className="shrink-0"
              size="lg"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  Start research
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}

function FormStep({
  step,
  title,
  description,
  icon: Icon,
  accent,
  children,
}: {
  step: number;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: "sky" | "violet";
  children: React.ReactNode;
}) {
  const accentStyles = {
    sky: "bg-sky-500/10 text-sky-700 ring-sky-500/20",
    violet: "bg-violet-500/10 text-violet-700 ring-violet-500/20",
  }[accent];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold ring-1",
              accentStyles,
            )}
          >
            {step}
          </span>
          <div className="min-w-0 flex-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <Icon className="h-4 w-4 text-muted-foreground" />
              {title}
            </CardTitle>
            <CardDescription className="mt-1">{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}
