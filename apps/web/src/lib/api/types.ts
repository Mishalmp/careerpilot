import type { components } from "./schema";

type Schemas = components["schemas"];

export type Status = Schemas["Status"];
export type JobSummary = Schemas["JobSummary"];
export type JobDetail = Schemas["JobDetail"];
export type JobCreate = Schemas["JobCreate"];
export type LinkResult = Schemas["LinkResult"];
export type JobUpdate = Schemas["JobUpdate"];
export type ApplicationUpdate = Schemas["ApplicationUpdate"];
export type ContactCreate = Schemas["ContactCreate"];
export type Topic = Schemas["TopicOut"];
export type Day = Schemas["DayOut"];
export type TodayPrep = Schemas["TodayPrep"];
export type TopicStatus = Schemas["TopicStatus"];
export type DayStatus = Schemas["DayStatus"];
export type StudyKind = Schemas["StudyKind"];
export type WorkMode = Schemas["WorkMode"];
export type Region = Schemas["Region"];
export type PortalMode = Schemas["PortalMode"];
export type EmailMode = Schemas["EmailMode"];
export type ContactKind = Schemas["ContactKind"];
