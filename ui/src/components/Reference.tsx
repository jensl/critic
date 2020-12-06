// This is a comment
/* this is also a comment */

import React from "react";
import clsx from "clsx";
import { Link } from "react-router-dom";

import { makeStyles } from "@material-ui/core/styles";

import Registry from ".";

const useStyles = makeStyles((theme) => ({
  reference: {
    ...theme.critic.monospaceFont,
    fontWeight: 500,
    background: theme.palette.secondary.light,
    borderColor: theme.palette.secondary.main,
    borderWidth: 1,
    borderStyle: "solid",
    borderRadius: 4,
    padding: "3px 6px 1px 6px",
    lineHeight: "1.5",
  },
  link: {
    color: "inherit",
    textDecoration: "none",

    "&:hover": {
      textDecoration: "underline",
    },
  },
}));

type Props = {
  className?: string;
  linkTo?: string;
};

const Reference: React.FunctionComponent<Props> = ({
  className,
  linkTo,
  children,
}) => {
  const classes = useStyles();
  const reference = (
    <code className={clsx(!linkTo && className, classes.reference)}>
      {children}
    </code>
  );
  if (linkTo)
    return (
      <Link className={clsx(className, classes.link)} to={linkTo}>
        {reference}
      </Link>
    );
  return reference;
};

export default Registry.add("Reference", Reference);
