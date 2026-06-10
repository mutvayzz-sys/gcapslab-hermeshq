import account from "./account";
import agent from "./agent";
import agents from "./agents";
import common from "./common";
import comms from "./comms";
import dashboard from "./dashboard";
import email from "./email";
import login from "./login";
import mfa from "./mfa";
import nav from "./nav";
import nodes from "./nodes";
import providers from "./providers";
import schedules from "./schedules";
import settings from "./settings";
import shell from "./shell";
import tasks from "./tasks";
import users from "./users";

const es: Record<string, string> = {
  ...account,
  ...agent,
  ...agents,
  ...common,
  ...comms,
  ...dashboard,
  ...email,
  ...login,
  ...mfa,
  ...nav,
  ...nodes,
  ...providers,
  ...schedules,
  ...settings,
  ...shell,
  ...tasks,
  ...users,
};

export default es;
